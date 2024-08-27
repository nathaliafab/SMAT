import json
import logging
import os
from typing import List

import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from mlc_chat import ChatModule
from nimrod.core.merge_scenario_under_analysis import MergeScenarioUnderAnalysis
from nimrod.test_suite_generation.generators.test_suite_generator import TestSuiteGenerator

class CodellamaTestSuiteGenerator(TestSuiteGenerator):

    def get_generator_tool_name(self) -> str:
        return "CODELLAMA"


    def _get_test_suite_class_paths(self, path: str) -> List[str]:
        paths = []
        for root, _, files in os.walk(path):
            paths.extend(os.path.join(root, file) for file in files if file.endswith(".java"))
        return paths


    def _get_test_suite_class_names(self, test_suite_path: str) -> List[str]:
        return [os.path.basename(path).replace(".java", "") for path in self._get_test_suite_class_paths(test_suite_path)]
    

    def create_chat_module(self, mpath: str, lpath: str, model: str, lib: str) -> ChatModule:
        return ChatModule(
            model=f"{mpath}/{model}",
            model_lib_path=f"{lpath}/{lib}",
        )


    def reset_chat_module(self, chat_module: ChatModule) -> None:
        chat_module.reset_chat()


    def generate_output(self, chat_module: ChatModule, prompt: str) -> str:
        return chat_module.generate(prompt=prompt)


    def save_output(self, prompt: str, output: str, dir: str, output_file_name: str) -> None:
        llm_outputs_dir = os.path.join(dir, "llm_outputs")
        output_file_path = os.path.join(llm_outputs_dir, f"{output_file_name}.txt")
        os.makedirs(llm_outputs_dir, exist_ok=True)
        with open(output_file_path, "w") as file:
            file.write(prompt + output)


    def parse_code(self, file_path: str) -> tuple:
        JAVA_LANGUAGE = Language(tsjava.language())
        parser = Parser(JAVA_LANGUAGE)
        with open(file_path, 'r') as f:
            source_code = f.read()
        tree = parser.parse(bytes(source_code, "utf8"))
        return JAVA_LANGUAGE, source_code, tree
    

    def extract_snippet(self, source_code: str, start_byte: int, end_byte: int) -> str:
        return source_code[start_byte:end_byte]


    def get_class_info(self, file_path: str, method_name: str, full_class_name: str) -> tuple:
        class_name = full_class_name.split('.')[-1]
        JAVA_LANGUAGE, source_code, tree = self.parse_code(file_path)

        query_text = """
            (class_declaration name: (identifier) @class_name)
                (field_declaration) @field_declaration
                (constructor_declaration) @constructor_declaration
                (method_declaration) @method_def
        """
        query = JAVA_LANGUAGE.query(query_text)
        captures = query.captures(tree.root_node)

        class_attributes = []
        class_constructors = []
        class_method = ""
        found_class = False

        for node, capture_name in captures:
            captured_text = self.extract_snippet(source_code, node.start_byte, node.end_byte)

            if capture_name == "class_name":
                if captured_text == class_name:
                    found_class = True
                elif found_class:
                    # Stop processing if we encounter a different class after finding the target class
                    break
                continue

            if found_class:
                if capture_name == "field_declaration":
                    class_attributes.append(captured_text)
                elif capture_name == "constructor_declaration":
                    class_constructors.append(captured_text)
                elif capture_name == "method_def" and method_name in captured_text:
                    class_method = captured_text

        return class_attributes, class_constructors, class_method


    def generate_prompts(self, prompts_file: str, class_name: str, methods: List[str], file_path: str) -> None:
        prompts = []

        for method in methods:
            try:
                class_attributes, constructor_codes, method_code = self.get_class_info(file_path, method, class_name)

                class_attributes_str = '\n'.join(class_attributes) if class_attributes else ""
                constructor_code_str = '\n'.join(constructor_codes) if constructor_codes else ""
                method_code_str = ''.join(method_code)

                prompt = (
                    f"/*\n{class_attributes_str}\n\n{constructor_code_str}\n\n{method_code_str}\n*/\n\n"
                    "import org.junit.FixMethodOrder;\n"
                    "import org.junit.Test;\n"
                    "import org.junit.runners.MethodSorters;\n"
                    "import static org.junit.Assert.*;\n\n"
                    "@FixMethodOrder(MethodSorters.NAME_ASCENDING)\n"
                    f"public class {class_name.split('.')[-1]}_{method.split('(')[0]}Test {{\n"
                    "//continue the test with code only:\n"
                )
                
                prompts.append(prompt)

            except Exception as e:
                logging.error("Error while generating prompt for method %s: %s", method, e)

        with open(prompts_file, "w") as file:
            json.dump(prompts, file, indent=4)


    def get_imports(self, file_path: str) -> List[str]:
        JAVA_LANGUAGE, source_code, tree = self.parse_code(file_path)

        query_text = """
        (import_declaration) @import
        (package_declaration) @package
        """
        query = JAVA_LANGUAGE.query(query_text)
        captures = query.captures(tree.root_node)

        imports = []
        
        for node, capture_name in captures:
            start_byte, end_byte = node.start_byte, node.end_byte
            captured_text = source_code[start_byte:end_byte].strip()

            if capture_name == "import":
                imports.append(f'{captured_text}\n')
            elif capture_name == "package":
                package_name = captured_text.split()[1].rstrip(';')
                imports.append(f'import {package_name}.*;\n')

        return imports


    def read_prompts(self, file_path):
        with open(file_path, "r") as file:
            prompts = json.load(file)
        
        return prompts


    def get_individual_tests(self, output_path: str, prompt: str, class_name: str, imports: str, i: int) -> None:
        llm_outputs_path = os.path.join(output_path, "llm_outputs")
        counter = 0

        def classify_annotations(captures, source_code):
            before_block = []
            test_block = []

            for node, _ in captures:
                captured_text = self.extract_snippet(source_code, node.start_byte, node.end_byte)
                if "@Test" in captured_text:
                    test_block.append({"snippet": captured_text})
                elif any(annotation in captured_text for annotation in ["@Before", "@BeforeClass", "@BeforeAll"]):
                    before_block.append({"snippet": captured_text})

            return before_block, test_block

        for file in os.listdir(llm_outputs_path):
            if file.endswith(".txt") and file.startswith(f"{i}"):
                file_path = os.path.join(llm_outputs_path, file)
                JAVA_LANGUAGE, source_code, tree = self.parse_code(file_path)

                query_text = """
                (method_declaration
                    (modifiers
                        (marker_annotation))) @method_def
                """
                query = JAVA_LANGUAGE.query(query_text)
                captures = query.captures(tree.root_node)

                before_block, test_block = classify_annotations(captures, source_code)

                for test in test_block:
                    method_name = f"{class_name.split('.')[-1]}Test_{i}_{counter}"
                    output_file_path = os.path.join(output_path, f"{method_name}.java")

                    new_prompt = prompt.split("public class")[0] + f"public class {method_name} {{\n"
                    full_prompt = "".join(imports) + new_prompt

                    if before_block:
                        full_prompt += "".join(before['snippet'] for before in before_block)

                    snippet = test['snippet']
                    test_method_name = snippet.split('(')[0].split()[-1]
                    new_snippet = snippet.replace(test_method_name, f"test{i}{counter}")

                    with open(output_file_path, "w") as f:
                        f.write(full_prompt + new_snippet + "\n}")

                    counter += 1

    
    def find_source_code_paths(self, jar_path: str, class_name: str) -> dict:
        return {"base": "/mnt/c/Users/natha/Downloads/smat/base.java",
                "left": "/mnt/c/Users/natha/Downloads/smat/left.java",
                "right": "/mnt/c/Users/natha/Downloads/smat/right.java",
                "merge": "/mnt/c/Users/natha/Downloads/smat/merge.java"}
        # Dividir o caminho em partes
        path_parts = jar_path.split(os.sep)
        
        # Verificar se a estrutura do caminho é a esperada
        if "transformed" not in path_parts:
            raise ValueError("O caminho fornecido não contém a parte 'transformed'.")
        
        # Encontrar o índice da parte "transformed"
        transformed_index = path_parts.index("transformed")
        
        # Substituir "transformed" por "source" e remover todas as partes subsequentes
        source_path_parts = path_parts[:transformed_index] + ["source"]
        
        # Construir o caminho base
        base_path = os.path.join("/", *source_path_parts)

        # Verificar se o diretório base existe antes de procurar
        if not os.path.exists(base_path):
            raise FileNotFoundError(f"O diretório base não existe: {base_path}")
        
        # Inicializar dicionário para armazenar caminhos de arquivos
        java_files = {"base": "", "left": "", "right": "", "merge": ""}
        
        # Procurar por arquivos .java recursivamente
        for root, dirs, files in os.walk(base_path):
            # Verificar se a pasta com o nome da classe existe e dar preferência aos arquivos dentro dela
            if os.path.basename(root) == class_name:
                for file in files:
                    if file.endswith(".java"):
                        file_key = file.replace(".java", "")
                        if file_key in java_files:
                            java_files[file_key] = os.path.join(root, file)

            # Verificar arquivos fora da pasta com o nome da classe
            for file in files:
                if file.endswith(".java"):
                    file_key = file.replace(".java", "")
                    if file_key in java_files and not java_files[file_key]:
                        java_files[file_key] = os.path.join(root, file)
                if all(java_files.values()):
                    break

        # Verifica se todos os arquivos foram encontrados, caso contrário, lança um erro
        missing_files = [key for key, value in java_files.items() if not value]
        if missing_files:
            raise FileNotFoundError(f"Os seguintes arquivos não foram encontrados: {', '.join(missing_files)}")

        return java_files
    

    def get_branch_info(self, input_jar: str, class_name: str) -> tuple:
        source_code_paths = self.find_source_code_paths(input_jar, class_name.split('.')[-1])
        branches = ["base", "left", "right", "merge"]

        branch = next((b for b in branches if b in input_jar), None)
        
        if branch:
            file_path = source_code_paths.get(branch)
            if file_path:
                return file_path, branch

        available_branches = ", ".join(branches)
        raise ValueError(f"No corresponding branch found in '{input_jar}'. Available branches: {available_branches}")


    def _execute_tool_for_tests_generation(self, input_jar: str, output_path: str, scenario: MergeScenarioUnderAnalysis, use_determinism: bool) -> None:
        class_name, methods = next(iter(scenario.targets.items()))
        model_info = {
            "mpath": "/home/nfab/dist",
            "lpath": "/home/nfab/dist/libs",
            "model": "CodeLlama-7b-Instruct-hf-q4f16_1-MLC",
            "lib": "CodeLlama-7b-Instruct-hf-q4f16_1-cuda.so"
        }
        prompts_path = os.path.join(output_path, "prompts.json")

        file_path, branch = self.get_branch_info(input_jar, class_name)
        self.generate_prompts(prompts_path, class_name, methods, file_path)
        imports = self.get_imports(file_path)
        prompts_list = self.read_prompts(prompts_path)

        cm = self.create_chat_module(**model_info)

        for i, prompt in enumerate(prompts_list):
            self._process_prompts(prompt, output_path, branch, class_name, imports, i, cm)

    def _process_prompts(self, prompt: str, output_path: str, branch: str, class_name: str, imports: str, i: int, cm, num_outputs=5) -> None:
        for j in range(num_outputs):
            output_file_name = f"{i}{j}_{branch}_{class_name.split('.')[-1]}"
            try:
                logging.debug("Generating output %d%d in branch \"%s\"", i, j, branch)
                output = self.generate_output(cm, prompt)
                self.save_output(prompt, output, output_path, output_file_name)
            except Exception as e:
                logging.error("Error while generating output %d%d in branch \"%s\": %s", i, j, branch, e)
            finally:
                self.reset_chat_module(cm)

        self.get_individual_tests(output_path, prompt, class_name, imports, i)
