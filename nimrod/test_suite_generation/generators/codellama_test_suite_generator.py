import os
from typing import Dict, List
from nimrod.core.merge_scenario_under_analysis import MergeScenarioUnderAnalysis

from nimrod.test_suite_generation.generators.test_suite_generator import \
    TestSuiteGenerator
from nimrod.tools.java import Java
from nimrod.utils import generate_classpath

from mlc_chat import ChatModule


class CodellamaTestSuiteGenerator(TestSuiteGenerator):
    TARGET_METHODS_LIST_FILENAME = 'methods_to_test.txt'
    TARGET_CLASS_LIST_FILENAME = 'classes_to_test.txt'

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
            class_fqcn = os.path.relpath(class_path, os.path.join(
                test_suite_path, "codellama-tests")).replace(os.sep, ".")
            class_names.append(class_fqcn[:-5])

        return class_names

    def generate_prompts(self, prompts_file, class_name, methods, code):
        for method in methods:
            temp_method = method.split("(")[0]

            try:
                with open(code, 'r') as file:
                    lines = file.readlines()

                method_found = False
                method_code = []
                for line in lines:
                    if temp_method in line and ("private" in line or "public" in line):
                        method_found = True
                    elif temp_method not in line and ("private" in line or "public" in line):
                        if method_found:
                            break
                    if method_found:
                        method_code.append(line)

                if method_found:
                    modified_lines = []
                    modified_lines.append(f"/*{''.join(method_code)}*/\n\n")
                    modified_lines.append("import org.junit.FixMethodOrder;\n")
                    modified_lines.append("import org.junit.Test;\n")
                    modified_lines.append("import org.junit.runners.MethodSorters;\n\n")
                    print(f"Generating prompt for method {method}")
                    modified_lines.append(f"@FixMethodOrder(MethodSorters.NAME_ASCENDING)\n")
                    modified_lines.append(f"public class {class_name}Test {{\n")
                    modified_lines.append(f"    public static boolean debug = false;\n\n")
                    modified_lines.append(f"    @Test\n")
                    modified_lines.append(f"    public void {temp_method}_001() throws Throwable {{\n")
                    modified_lines.append(f"        if (debug) {{\n")
                    modified_lines.append(f"\"\"\"\n")
                
                    with open(prompts_file, "w") as file:
                        file.writelines(modified_lines)

            except Exception as e:
                print(f"Error while generating prompt for method {method}: {e}")

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


    def generate_output(self, chat_module, prompt):
        return chat_module.generate(prompt=prompt)


    def save_output(self, prompt, output, dir, output_file_name):
        if dir:
            if not os.path.exists(dir):
                os.makedirs(dir)

        output_file_path = f"{dir}/{output_file_name}.txt"
        with open(output_file_path, "w") as f:
            f.write(prompt + "\n" + output)


    def reset_chat_module(self, chat_module):
        chat_module.reset_chat()

    def _execute_tool_for_tests_generation(self, input_jar: str, output_path: str, scenario: MergeScenarioUnderAnalysis, use_determinism: bool) -> None:
        class_name, methods = list(scenario.targets.items())[0]
         
        mpath = "/home/nfab/dist"
        lpath = "/home/nfab/dist/libs"
        model = "CodeLlama-7b-Instruct-hf-q4f16_1-MLC"
        lib = "CodeLlama-7b-Instruct-hf-q4f16_1-cuda.so"
        outputs_dir = f"{output_path}"
        prompts_path = f"{output_path}/prompts.txt"

        #code_base = f"/mnt/c/Users/natha/Downloads/mergedataset/mergedataset/spring-boot/ea8107b6a53fa60b5f23b33e1b6d2e88bb60133c/source/UndertowEmbeddedServletContainerFactory_base.java"
        code_left = f"/mnt/c/Users/natha/Downloads/mergedataset/mergedataset/spring-boot/ea8107b6a53fa60b5f23b33e1b6d2e88bb60133c/source/UndertowEmbeddedServletContainerFactory_left.java"
        #code_right = f"/mnt/c/Users/natha/Downloads/mergedataset/mergedataset/spring-boot/ea8107b6a53fa60b5f23b33e1b6d2e88bb60133c/source/UndertowEmbeddedServletContainerFactory_right.java"
        #code_merge = f"/mnt/c/Users/natha/Downloads/mergedataset/mergedataset/spring-boot/ea8107b6a53fa60b5f23b33e1b6d2e88bb60133c/source/UndertowEmbeddedServletContainerFactory_merge.java"

        self.generate_prompts(prompts_path, class_name, methods, code_left)
        prompts_list = self.read_prompts(prompts_path)
        
        cm = self.create_chat_module(mpath, lpath, model, lib)

        for i, prompt in enumerate(prompts_list):
            for j in range(0, 2):
                print(f"----------------------------- Generating output {i}-{j}")
                output_file_name = f"output{i}-{j}"
                output = self.generate_output(cm, prompt)
                self.save_output(prompt, output, outputs_dir, output_file_name)
                self.reset_chat_module(cm)