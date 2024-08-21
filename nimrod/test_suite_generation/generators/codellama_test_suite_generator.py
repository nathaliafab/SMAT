import os, logging
from typing import List, Generator
import tree_sitter_java as tsjava
from tree_sitter import Language, Parser, Node, Tree
from nimrod.core.merge_scenario_under_analysis import MergeScenarioUnderAnalysis
from nimrod.test_suite_generation.generators.test_suite_generator import \
    TestSuiteGenerator

from mlc_chat import ChatModule

class CodellamaTestSuiteGenerator(TestSuiteGenerator):

    def get_generator_tool_name(self) -> str:
        return "CODELLAMA"

    def _get_test_suite_class_paths(self, path: str) -> List[str]:
        paths = []

        for node in os.listdir(path):
            if os.path.isdir(os.path.join(path, node)):
                paths += self._get_test_suite_class_paths(os.path.join(path, node))
            elif node.endswith(".java"):
                paths.append(os.path.join(path, node))

        return paths


    def _get_test_suite_class_names(self, test_suite_path: str) -> List[str]:
        class_names = []

        for class_path in self._get_test_suite_class_paths(test_suite_path):
            class_fqcn = os.path.basename(class_path).replace(".java", "")
            class_names.append(class_fqcn)

        return class_names


    def get_method_code(self, file_path, method_name, full_class_name):
        JAVA_LANGUAGE = Language(tsjava.language())
        parser = Parser(JAVA_LANGUAGE)
    
        class_name = full_class_name.split('.')[-1]
        source_code = open(file_path).read()
        tree = parser.parse(bytes(source_code, "utf8"))

        def traverse_tree(tree: Tree) -> Generator[Node, None, None]:
            cursor = tree.walk()
            visited_children = False

            while True:
                if not visited_children:
                    yield cursor.node
                    visited_children = not cursor.goto_first_child()
                elif cursor.goto_next_sibling():
                    visited_children = False
                elif not cursor.goto_parent():
                    break

        def get_snippet(start, end):
            return '\n'.join([line[start.column:] if i == start.row else line[:end.column] if i == end.row else line
                for i, line in enumerate(source_code.splitlines()) 
                if start.row <= i <= end.row])

        def get_class_node(tree: Tree) -> list:
            classes = [node for node in traverse_tree(tree) if node.type == 'class_declaration']
            for class_node in classes:
                for child in class_node.children:
                    if child.type == 'identifier':
                        start = child.start_point
                        end = child.end_point
                        child_class_name = get_snippet(start, end).split()[0]
                        if child_class_name == class_name:
                            return class_node
            return None
        
        def get_class_attributes_nodes(class_node: Node) -> list:
            for child in class_node.children:
                if child.type == 'class_body':
                    attributes = [node for node in child.children if node.type == 'field_declaration']
                    break
            return attributes if attributes else None
        
        def get_constructor_nodes(class_node: Node) -> list:
            for child in class_node.children:
                if child.type == 'class_body':
                    constructors = [node for node in child.children if node.type == 'constructor_declaration']
                    break
            return constructors if constructors else None

        def get_method_node(class_node: Node) -> list:
            for child in class_node.children:
                if child.type == 'class_body':
                    methods = [node for node in child.children if node.type == 'method_declaration']
                    break

            for method in methods:
                for child in method.children:
                    if child.type == 'identifier':
                        start = child.start_point
                        end = child.end_point
                        child_method_name = get_snippet(start, end).split()[0]
                        if child_method_name == method_name:
                            return method
            return None
        
        class_node = get_class_node(tree)
        class_attributes = [get_snippet(attribute.start_point, attribute.end_point) for attribute in get_class_attributes_nodes(class_node)]
        constructor_codes = [get_snippet(constructor.start_point, constructor.end_point) for constructor in get_constructor_nodes(class_node)]
        method_node = get_method_node(class_node)
        method_code = get_snippet(method_node.start_point, method_node.end_point)

        return class_attributes, constructor_codes, method_code


    def generate_prompts(self, prompts_file, class_name, methods, code):
        for method in methods:
            try:
                class_attributes, constructor_codes, method_code = self.get_method_code(code, method, class_name)

                modified_lines = []
                class_attributes_str = '\n'.join(class_attributes)
                method_code_str = ''.join(method_code)

                if constructor_codes:
                    constructor_code_str = '\n'.join(constructor_codes)
                    modified_lines.append(f"/*\n{class_attributes_str}\n\n{constructor_code_str}\n\n{method_code_str}")
                else:
                    modified_lines.append(f"/*\n{class_attributes_str}\n\n{method_code_str}")

                modified_lines.append("\n*/\n\n")
                modified_lines.append("import org.junit.FixMethodOrder;\n")
                modified_lines.append("import org.junit.Test;\n")
                modified_lines.append("import org.junit.runners.MethodSorters;\n")
                modified_lines.append("import static org.junit.Assert.*;\n\n")
                modified_lines.append(f"@FixMethodOrder(MethodSorters.NAME_ASCENDING)\n")
                modified_lines.append(f"public class {class_name.split('.')[-1]}_{method.split('(')[0]}Test {{\n")
                modified_lines.append(f"//continue the test with code only:\n")
                modified_lines.append(f"\"\"\"")
                
                with open(prompts_file, "w") as file:
                    file.writelines(modified_lines)

            except Exception as e:
                logging.error("Error while generating prompt for method %s: %s", method, e)


    def get_imports(self, code):
        with open(code, 'r') as file:
            lines = file.readlines()

        imports = []
        for line in lines:
            if line.strip().startswith("import"):
                imports.append(line)
            elif line.strip().startswith("package"):
                package_name = line.split()[1].rstrip(';')
                imports.append(f'import {package_name}.*;\n')

        return imports


    def read_prompts(self, file_path):
        prompts = []
        current_prompt = ""

        with open(file_path, "r") as file:
            lines = file.readlines()
            
            for line in lines:
                if line.strip() != '"""':
                    current_prompt += line
                else:
                    if current_prompt.strip() != "":
                        prompts.append(current_prompt)
                        current_prompt = ""

        return prompts


    def create_chat_module(self, mpath, lpath, model, lib):
        return ChatModule(
            model=f"{mpath}/{model}",
            model_lib_path=f"{lpath}/{lib}",
        )


    def reset_chat_module(self, chat_module):
        chat_module.reset_chat()


    def generate_output(self, chat_module, prompt):
        return chat_module.generate(prompt=prompt)


    def save_output(self, prompt, output, dir, output_file_name):
        if dir:
            if not os.path.exists(dir):
                os.makedirs(dir)
            if not os.path.exists(f"{dir}/llm_outputs"):
                os.makedirs(f"{dir}/llm_outputs")

        output_file_path = f"{dir}/llm_outputs/{output_file_name}.txt"
        with open(output_file_path, "w") as f:
            f.write(prompt + output)


    def get_branch(self, input_jar, code_paths):
        branches = ["base", "left", "right", "merge"]
        for branch in branches:
            if branch in input_jar:
                return code_paths[branch], branch
        raise ValueError(f"Nenhuma correspondência de branch encontrada no caminho: {input_jar}")


    def get_individual_tests(self, output_path, prompt, class_name, imports, i):
        llm_outputs_path = f"{output_path}/llm_outputs/"

        JAVA_LANGUAGE = Language(tsjava.language())
        parser = Parser(JAVA_LANGUAGE)

        for file in os.listdir(llm_outputs_path):
            if file.endswith(".txt") and file.startswith(f"{i}"):
                source_code = open(os.path.join(llm_outputs_path, file)).read()
                tree = parser.parse(bytes(source_code, "utf8"))

                def traverse_tree(tree: Tree) -> Generator[Node, None, None]:
                    cursor = tree.walk()
                    visited_children = False

                    while True:
                        if not visited_children:
                            yield cursor.node
                            visited_children = not cursor.goto_first_child()
                        elif cursor.goto_next_sibling():
                            visited_children = False
                        elif not cursor.goto_parent():
                            break

                def collect_methods(tree: Tree) -> list:
                    methods = [node for node in traverse_tree(tree) if node.type == 'method_declaration']
                    return methods

                def has_missing_brace(body: Node):
                    if body.children[-1].start_point.column == body.children[-1].end_point.column:
                        return True
                    return False
                
                def separate_tests(methods):
                    before_block = []
                    test_block = []

                    def get_snippet(start, end):
                        return '\n'.join([line[start.column:] if i == start.row else line[:end.column] if i == end.row else line
                                            for i, line in enumerate(source_code.splitlines()) 
                                            if start.row <= i <= end.row])

                    for method in methods:
                        children = method.children
                        for child in children:
                            if child.type == 'modifiers':
                                if child.children[0].type == 'marker_annotation':
                                    start = child.children[0].start_point
                                    end = child.children[0].end_point
                                    
                                    annotation_snippet = get_snippet(start, end)
                    
                                    if annotation_snippet in ["@Before", "@BeforeEach", "@BeforeAll", "@BeforeClass"]:
                                        start = method.start_point
                                        end = method.end_point
                                        before_block.append({"snippet": get_snippet(start, end), "missing_braces": has_missing_brace(method.children[-1])})
                                    
                                    elif annotation_snippet == "@Test":
                                        start = method.start_point
                                        end = method.end_point
                                        test_block.append({"snippet": get_snippet(start, end), "missing_braces": has_missing_brace(method.children[-1])})

                    print(before_block)
                    print(test_block)
                    return before_block, test_block

                methods = collect_methods(tree)
                before_block, test_block = separate_tests(methods)

                for k, test in enumerate(test_block):
                    method_name = f"{class_name.split('.')[-1]}Test_{i}_{k}"
                    file_path = f"{output_path}/{method_name}.java"
                    
                    with open(file_path, "w") as f:
                        new_prompt = prompt.split("public class")[0]
                        new_prompt += f"public class {method_name} {{\n"
                        full_prompt = "".join(imports) + new_prompt
                        
                        if before_block:
                            for before in before_block:
                                full_prompt += "".join(before['snippet'])
                        
                        snippet = test['snippet']
                        test_signature = snippet.split("{")[0].strip()
                        new_signature = f"public void test{i}{k}()"
                        new_snippet = snippet.replace(test_signature, new_signature, 1)

                        f.write(full_prompt + new_snippet)
                        
                        if test['missing_braces']:
                            f.write("}")
                        f.write("}\n")

    
    def find_source_code_paths(self, jar_path, class_name):
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

    def _execute_tool_for_tests_generation(self, input_jar: str, output_path: str, scenario: MergeScenarioUnderAnalysis, use_determinism: bool) -> None:
        class_name, methods = list(scenario.targets.items())[0]
         
        mpath = "/home/nfab/dist"
        lpath = "/home/nfab/dist/libs"
        model = "CodeLlama-7b-Instruct-hf-q4f16_1-MLC"
        lib = "CodeLlama-7b-Instruct-hf-q4f16_1-cuda.so"
        prompts_path = f"{output_path}/prompts.txt"
        code_paths = self.find_source_code_paths(input_jar, class_name.split('.')[-1])
        code, branch = self.get_branch(input_jar, code_paths)

        self.generate_prompts(prompts_path, class_name, methods, code)
        imports = self.get_imports(code)

        prompts_list = self.read_prompts(prompts_path)
        
        cm = self.create_chat_module(mpath, lpath, model, lib)

        for i, prompt in enumerate(prompts_list):
            for j in range(0, 5):
                try:
                    logging.debug("Generating output %d%d in branch \"%s\"", i, j, branch)
                    output_file_name = f"{i}{j}_{branch}_{class_name.split('.')[-1]}"
                    output = self.generate_output(cm, prompt)
                    self.save_output(prompt, output, output_path, output_file_name)
                    self.reset_chat_module(cm)
                except Exception as e:
                    logging.error("Error while generating output %d%d in branch \"%s\": %s", i, j, branch, e)
                    pass
            self.get_individual_tests(output_path, prompt, class_name, imports, i)