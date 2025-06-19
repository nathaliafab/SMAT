import json
import logging
import os
import requests
from typing import List, Dict, Union, Any, Optional
from itertools import combinations
import re

import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from nimrod.core.merge_scenario_under_analysis import MergeScenarioUnderAnalysis
from nimrod.test_suite_generation.generators.test_suite_generator import TestSuiteGenerator
from nimrod.tests.utils import get_config
from nimrod.utils import load_json, save_json


class Api:

    def __init__(self, api_url: str, timeout_seconds: int, temperature: float, seed: int, model: str) -> None:
        self.api_url = api_url
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.seed = seed
        self.model = model
        self.headers = {"Content-Type": "application/json"}
        self.payload = {
            "model": self.model,
            "messages": [],
            "stream": False,
            "options": {
                "temperature": self.temperature, 
                "num_ctx": 16384,
                "seed": self.seed,
            },
        }
        self.branch = None
    
    def set_branch(self, branch: str) -> None:
        """Sets the branch to be used in the API requests."""
        self.branch = branch

    def post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Sends a POST request to the API and handles the response."""
        try:
            response: requests.Response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=self.timeout_seconds
            )
            response.raise_for_status()
            logging.debug("Request successful. Status: %s", response.status_code)
            return response.json()
        except requests.exceptions.Timeout:
            logging.error("Request timed out.")
            return {"error": "Request timed out"}
        except requests.exceptions.RequestException as e:
            logging.error(f"Request error: {e}")
            return {"error": "Request error"}
        except json.JSONDecodeError:
            logging.error("JSON decoding error.")
            return {"error": "JSON decoding error"}
    
    def set_payload_messages(self, messages: List[Dict[str, str]]) -> None:
        """Sets the messages in the payload."""
        self.payload["messages"] = messages

    def generate_output(self, messages: List[Dict[str, str]]) -> Dict[str, Union[str, int]]:
        """Generates output by sending messages to the API."""
        try:
            self.set_payload_messages(messages)
            response = self.post(self.payload)
            #logging.debug("Response: %s", response)
            return {
                "response": response.get("message", {}).get("content", "Response not found."),
                "total_duration": response.get("total_duration", self.timeout_seconds),
            }
        except Exception as e:
            logging.error(f"Error generating output: {e}")
            return {"error": "Output generation error"}
        
    def generate_messages_list(self, method_info: Dict[str, str], full_class_name: str,
                               branch: str, output_path: str) -> Dict[str, List[Dict[str, str]]]:
        """
        Generates the messages for the API requests.
        Each list of messages contains different information about the method under test.
        """
        self.set_branch(branch)  # Set the branch
        class_name = full_class_name.split('.')[-1]
        method_name = method_info.get("method_name", "")
        class_fields = method_info.get("class_fields", [])
        constructor_codes = method_info.get("constructor_codes", [])
        method_code = method_info.get("method_code", "")
        left_changes_summary = method_info.get("left_changes_summary", "")
        right_changes_summary = method_info.get("right_changes_summary", "")


        ######################################################
        ## PROMPTS INCREMENTAL COMBINATIONS
        system_message = {
            "role": "system",
            "content": (
                "You are a senior Java developer with expertise in JUnit testing.\n"
                "Your task is to provide JUnit tests for the given method in the class under test, "
                "considering the changes introduced in the left and right branches.\n"
                "You have to answer with the test code only, inside code blocks (```).\n"
                "The tests should start with @Test."
            ),
        }

        user_init_msg = {
            "role": "user",
            "content": f"""Here is the context of the method under test in the class {class_name} on the {branch} branch:""",
        }

        user_msg_templates = [
            {"role": "user", "content": f"{left_changes_summary}\n{right_changes_summary}"},
            {"role": "user", "content": f"Class fields:\n" + "\n".join(class_fields)},
            {"role": "user", "content": f"Constructors:\n" + "\n".join(constructor_codes)},
        ]

        user_method_ctx_msg = {
                "role": "user",
                "content": (
                f"Target Method Under Test:\n{method_code}\n\n"
                "Now generate JUnit tests for the method under test, considering the given context. Remember to create meaningful assertions.\n"
                "Write all tests inside code blocks (```), and start each test with @Test."
            ),
        }

        messages_dict: Dict[str, List[Dict[str, str]]] = {}
        counter = 1

        ## PROMPT SEM CONTEXTO
        key = f"prompt{counter}"
        messages_list = [system_message, user_init_msg, user_method_ctx_msg]
        messages_dict[key] = messages_list
        counter += 1

        ## PROMPTS COM CONTEXTO
        for r in range(1, len(user_msg_templates) + 1):
            for user_msgs_combination in combinations(user_msg_templates, r):
                key = f"prompt{counter}"
                messages_list = [system_message, user_init_msg, *user_msgs_combination, user_method_ctx_msg]
                messages_dict[key] = messages_list
                counter += 1

        # Save messages to a JSON file
        output_file_path = os.path.join(output_path, "generated_messages.json")
        if os.path.exists(output_file_path):
            with open(output_file_path, "r") as file:
                existing_data = json.load(file)
        else:
            existing_data = {}

        if class_name not in existing_data:
            existing_data[class_name] = {}

        existing_data[class_name][method_info["method_name"]] = messages_dict

        with open(output_file_path, "w") as file:
            json.dump(existing_data, file, indent=4)

        return messages_dict


class CodellamaTestSuiteGenerator(TestSuiteGenerator):

    def get_generator_tool_name(self) -> str:
        return "CODELLAMA"

    def _get_test_suite_class_paths(self, path: str) -> List[str]:
        paths: List[str] = []
        for root, _, files in os.walk(path):
            paths.extend(os.path.join(root, file) for file in files if file.endswith(".java"))
        return paths

    def _get_test_suite_class_names(self, test_suite_path: str) -> List[str]:
        return [os.path.basename(path).replace(".java", "") for path in self._get_test_suite_class_paths(test_suite_path)]

    def save_output(self, test_template: str, output: str, dir: str, output_file_name: str) -> None:
        """Saves the output generated by the model to a file, replacing #TEST_METHODS# in the template."""
        # Remove content between <think> tags
        output = re.sub(r'<think>.*?</think>', '', output, flags=re.DOTALL)

        # Extract only the content inside ``` blocks (excluding the ``` markers)
        matches = re.findall(r'```(?:\w+)?\n?(.*?)```', output, flags=re.DOTALL)
        output = '\n'.join(matches).strip()

        # Remove lines starting with "number. <text>" (e.g., "1. public void test() {...}")
        output = re.sub(r"^\d+\.\s.*$", "", output, flags=re.MULTILINE)

        # Look for @Before, @BeforeClass first; fallback to @Test if none are found
        markers = ["@Before", "@BeforeClass", "@Test"]
        index = min((output.find(marker) for marker in markers if marker in output), default=-1)

        # Keep only the content starting from the first found annotation
        output = output[index:] if index != -1 else output

        llm_outputs_dir = os.path.join(dir, "llm_outputs")
        output_file_path = os.path.join(llm_outputs_dir, f"{output_file_name}.txt")
        filled_template = test_template.replace("#TEST_METHODS#", output)

        os.makedirs(llm_outputs_dir, exist_ok=True)
        with open(output_file_path, "w") as file:
            file.write(filled_template)

    def parse_code(self, source_code_path: str) -> tuple:
        """Parses the Java source code using the Tree-sitter parser and return the language, source code, and generated AST"""
        JAVA_LANGUAGE = Language(tsjava.language())
        parser = Parser(JAVA_LANGUAGE)
        with open(source_code_path, 'r') as f:
            source_code = f.read()
        tree = parser.parse(bytes(source_code, "utf8"))
        return JAVA_LANGUAGE, source_code, tree

    def extract_snippet(self, source_code: str, start_byte: int, end_byte: int) -> str:
        """Extracts a snippet of code from the source code using the start and end byte offsets"""
        return source_code[start_byte:end_byte]

    def extract_class_info(self, source_code_path: str, full_method_name: str, full_class_name: str) -> tuple:
        """
        Extracts the class fields, constructor, and body of the method under test from the source code
        using the generated AST to query the information
        """
        try:
            class_name = full_class_name.split('.')[-1]
            method_name = full_method_name.split('(')[0]
            JAVA_LANGUAGE, source_code, tree = self.parse_code(source_code_path)

            query_text = f"""
                (class_declaration
                    name: (identifier) @class_name
                    body: (class_body
                        [
                        (field_declaration) @field_declaration
                        (constructor_declaration
                            name: (identifier) @constructor_name) @constructor_declaration
                        (method_declaration
                            name: (identifier) @method_name) @method_def
                        (#eq? @method_name "{method_name}")
                        (#eq? @constructor_name "{class_name}")
                        ]
                    )
                    (#eq? @class_name "{class_name}")
                )
            """
            query = JAVA_LANGUAGE.query(query_text)
            captures = query.captures(tree.root_node)

            if not captures:
                raise Exception(f"No captures found for the class '{class_name}' in '{source_code_path}'")

            class_fields: List[str] = []
            class_constructors: List[str] = []
            class_method: str = ""

            for node, capture_name in captures:
                captured_text = self.extract_snippet(source_code, node.start_byte, node.end_byte)

                if capture_name == "field_declaration":
                    class_fields.append(captured_text)
                elif capture_name == "constructor_declaration":
                    class_constructors.append(captured_text)
                elif capture_name == "method_def":
                    class_method = captured_text

            return class_fields, class_constructors, class_method

        except Exception as e:
            logging.error(f"An error occurred while extracting class info for '{full_class_name}': {e}")
            raise e

    def save_scenario_infos(self, scenario_infos_path: str, class_name: str, methods: List[str], source_code_path: str) -> None:
        """Stores relevant scenario information (for each class and method) in a JSON file"""
        if os.path.exists(scenario_infos_path):
            scenario_infos_dict = load_json(scenario_infos_path)
        else:
            scenario_infos_dict = {}

        if class_name not in scenario_infos_dict:
            scenario_infos_dict[class_name] = []

        for method_item in methods:
            method = method_item.get("method", method_item)
            left_changes_summary = method_item.get("leftChangesSummary", "")
            right_changes_summary = method_item.get("rightChangesSummary", "")
            try:
                logging.debug("Saving scenario information for method '%s' in class '%s'", method, class_name)
                class_fields, constructor_codes, method_code = self.extract_class_info(source_code_path, method, class_name)

                scenario_infos_dict[class_name].append({
                    'class_fields': class_fields if class_fields else [],
                    'constructor_codes': constructor_codes if constructor_codes else [],
                    'method_name': method,
                    'method_code': method_code if method_code else "",
                    'left_changes_summary': left_changes_summary,
                    'right_changes_summary': right_changes_summary,
                    'test_template': (
                        "import org.junit.Test;\n"
                        "import org.junit.Before;\n"
                        "import org.junit.BeforeClass;\n"
                        "import static org.junit.Assert.*;\n\n"
                        f"public class {class_name.split('.')[-1]}_{method.split('(')[0]}Test {{\n"
                        "#TEST_METHODS#\n"
                        "}"
                    )
                })

            except Exception as e:
                logging.error("Error while saving scenario information for method '%s' in class '%s': %s", method, class_name, e)

        save_json(scenario_infos_path, scenario_infos_dict)

    def save_imports(self, class_name: str, source_code_path: str, imports_path: str) -> None:
        """Extracts import statements from the Java source code and stores them in a JSON file"""
        JAVA_LANGUAGE, source_code, tree = self.parse_code(source_code_path)

        query_text = """
        (import_declaration) @import
        (package_declaration) @package
        """
        query = JAVA_LANGUAGE.query(query_text)
        captures = query.captures(tree.root_node)

        if os.path.exists(imports_path):
            imports_dict = load_json(imports_path)
        else:
            imports_dict = {}

        class_imports = imports_dict.setdefault(class_name, [])

        for node, capture_name in captures:
            start_byte, end_byte = node.start_byte, node.end_byte
            captured_text = source_code[start_byte:end_byte].strip()

            if capture_name == "import":
                class_imports.append(f'{captured_text}\n')
            elif capture_name == "package":
                package_name = captured_text.split()[1].rstrip(';')
                class_imports.append(f'import {package_name}.*;\n')

        save_json(imports_path, imports_dict)

    def extract_individual_tests(self, output_path: str, test_template: str, class_name: str, imports: List[str], i: int, j: int, prompt_key: str, branch: str) -> None:
        """Extracts individual tests from the generated test suite and saves them to separate files"""
        llm_outputs_path = os.path.join(output_path, "llm_outputs")
        counter = 0

        def classify_annotations(captures: List[tuple], source_code: str) -> tuple:
            """Classifies annotations in the captured snippets as 'before' or 'test' blocks"""
            before_block: List[Dict[str, str]] = []
            test_block: List[Dict[str, str]] = []

            for node, _ in captures:
                captured_text = self.extract_snippet(source_code, node.start_byte, node.end_byte)
                if "@Test" in captured_text:
                    test_block.append({"snippet": captured_text})
                elif any(annotation in captured_text for annotation in ["@Before", "@BeforeClass"]):
                    before_block.append({"snippet": captured_text})

            return before_block, test_block

        # Format: {i}{j}_{branch}_{class_name.split('.')[-1]}_{prompt_key}.txt
        pattern = rf"^{i}{j}_(left|right)_{re.escape(class_name.split('.')[-1])}_{prompt_key}\.txt$"
        for file in os.listdir(llm_outputs_path):
            # Avoid processing the wrong files (from different classes)
            if re.match(pattern, file):
                logging.debug("Processing file: %s", file)
                source_code_path = os.path.join(llm_outputs_path, file)
                JAVA_LANGUAGE, source_code, tree = self.parse_code(source_code_path)

                # Tree-sitter query to find method definitions with annotations
                query_text = """
                (method_declaration
                    (modifiers [
                        (annotation)
                        (marker_annotation)
                        ]
                        )) @method_def
                """
                query = JAVA_LANGUAGE.query(query_text)
                captures = query.captures(tree.root_node)

                before_block, test_block = classify_annotations(captures, source_code)
                for test in test_block:
                    method_name = f"{class_name.split('.')[-1]}Test_{branch}_{prompt_key}_{j}_{i}_{counter}"
                    output_file_path = os.path.join(output_path, f"{method_name}.java")

                    new_template = test_template.split("public class")[0] + f"public class {method_name} {{\n"
                    full_template = "".join(imports) + new_template

                    if before_block:
                        full_template += "".join(before['snippet'] for before in before_block)

                    snippet = test['snippet']
                    public_index = snippet.find('public')
                    if public_index != -1:
                        test_method_name = snippet[public_index:].split('(')[0].split()[-1]
                        new_snippet = snippet.replace(test_method_name, f"test{i}{counter}")

                        with open(output_file_path, "w") as f:
                            f.write(full_template + new_snippet + "\n}")

                        counter += 1

    def find_source_code_paths(self, input_jar: str, jar_type: str, class_name: str, project_name: str) -> Dict[str, str]:
        """Finds the source code files for the given class name in the specified JAR path"""
        input_jar = input_jar.split(":")[0]
        if not os.path.exists(input_jar):
            logging.error("The provided jar path '%s' does not exist", input_jar)
            raise FileNotFoundError(f"The provided path '{input_jar}' does not exist")

        path_parts = input_jar.split(os.sep)
        if jar_type != "transformed" and jar_type != "original":
            raise ValueError("The provided path does not contain the expected jar type (transformed/original)")

        type_index = path_parts.index(jar_type)
        base_path = os.path.join("/", *path_parts[:type_index], "source")

        if not os.path.exists(base_path):
            raise FileNotFoundError(f"The base path '{base_path}' does not exist")

        java_files = {key: "" for key in ["base", "left", "right", "merge"]}

        for root, _, files in os.walk(base_path):
            java_candidates = [file for file in files if file.endswith(".java")]

            # Prioritize files within the class-named folder
            if os.path.basename(root) == class_name:
                for file in java_candidates:
                    file_key = file.replace(".java", "")
                    if file_key in java_files:
                        java_files[file_key] = os.path.join(root, file)

            # If any file is still missing, try to fill it in
            for file in java_candidates:
                file_key = file.replace(".java", "")
                if file_key in java_files and not java_files[file_key]:
                    java_files[file_key] = os.path.join(root, file)

        missing_files = [key for key, path in java_files.items() if not path]
        if missing_files:
            raise FileNotFoundError(f"The following source code files were not found: {', '.join(missing_files)}")

        return java_files

    def fetch_source_code_branch(self, input_jar: str, jar_type: str, class_name: str, project_name: str) -> tuple:
        """Retrieves the source code path and branch for the given JAR path"""
        source_code_paths = self.find_source_code_paths(input_jar, jar_type, class_name.split('.')[-1], project_name)
        branches = ["base", "left", "right", "merge"]

        branch = next((b for b in branches if b in input_jar), None)

        if branch:
            source_code_path = source_code_paths.get(branch)
            if source_code_path:
                return source_code_path, branch, source_code_paths

        available_branches = ", ".join(branches)
        raise ValueError(f"No corresponding branch found in '{input_jar}'. Available branches: {available_branches}")

    def record_output_duration(self, time_duration_path: str, output_path: str, class_name: str,
                               output_file_name: str, total_duration: int, project_name: str) -> None:
        """Records the duration of output generation for the given class and output file"""
        logging.debug("Recording duration for output '%s' in class '%s'", output_file_name, class_name)
        os.makedirs(os.path.dirname(time_duration_path), exist_ok=True)

        if not os.path.exists(time_duration_path):
            with open(time_duration_path, "w") as file:
                json.dump({}, file)

        time_duration_dict = load_json(time_duration_path)

        project_data = time_duration_dict.setdefault(project_name, {})
        class_data = project_data.setdefault(class_name, {"total_duration": 0, "outputs": {}})

        key_name = output_path.split(os.sep)[-1] + '_' + output_file_name

        total_duration_seconds = total_duration / 1_000_000_000

        duration_rounded = round(total_duration_seconds, 2)
        class_data["outputs"][key_name] = duration_rounded
        class_data["total_duration"] = round(class_data["total_duration"] + duration_rounded, 2)

        try:
            save_json(time_duration_path, time_duration_dict)
        except Exception as e:
            logging.error("Error while recording duration for output '%s' in class '%s': %s", output_file_name, class_name, e)
            raise

    def _execute_tool_for_tests_generation(self, input_jar: str, output_path: str, scenario: MergeScenarioUnderAnalysis, use_determinism: bool) -> None:
        config = get_config()
        api_params = config.get("api_params", {})
        if not api_params:
            raise ValueError("The 'api_params' section is missing from the configuration file")

        if not api_params.get("codellama"):
            raise ValueError("The 'codellama' section is missing from the 'api_params' configuration")

        codellama_params = api_params.get("codellama", {})
        self.api = Api(
            api_url=codellama_params.get("api_url", "http://localhost:11434/api/chat"),
            timeout_seconds=codellama_params.get("timeout_seconds", 60),
            temperature=codellama_params.get("temperature", 0),
            seed=codellama_params.get("seed", 42),
            model=codellama_params.get("model", "codellama:70b")
        )

        # Define paths for storing scenario information (for prompt generation),
        # importing data (to be extracted from source code), and recording time duration (for each output)
        scenario_infos_path = os.path.join(output_path, "scenario_infos.json")
        imports_path = os.path.join(output_path, "imports.json")
        # Save time duration data in the 'reports' folder, located next to the 'projects' folder
        time_duration_path = os.path.join(
            os.path.dirname(
                os.path.dirname(
                    os.path.dirname(output_path))), "reports", "codellama_time_duration.json")

        project_name = scenario.project_name
        targets = scenario.targets
        jar_type = scenario.jar_type

        # Fetch the source code paths for each class and save the associated scenario information and import data
        for class_name, methods in targets.items():
            source_code_path, branch, source_paths = self.fetch_source_code_branch(input_jar, jar_type, class_name, project_name)
            self.save_scenario_infos(scenario_infos_path, class_name, methods, source_code_path)
            self.save_imports(class_name, source_code_path, imports_path)

        # Load scenario information and import data into dictionaries
        scenario_infos_dict = load_json(scenario_infos_path)
        imports_dict = load_json(imports_path)

        # Generate tests for each method in every class and save the results
        for class_name, scenario_infos_list in scenario_infos_dict.items():
            logging.debug("Generating tests for target methods in class '%s'", class_name)
            for i, method_info in enumerate(scenario_infos_list):
                messages_list = self.api.generate_messages_list(method_info, class_name, branch, output_path)
                test_template = method_info.get("test_template", "")
                self._process_prompts(messages_list=messages_list, test_template=test_template, output_path=output_path,
                                      branch=branch, class_name=class_name, imports=imports_dict.get(class_name, []),
                                      i=i, time_duration_path=time_duration_path, project_name=project_name)

    def _process_prompts(self, messages_list: Dict[str, List[Dict[str, str]]], test_template: str, output_path: str, branch: str,
                         class_name: str, imports: List[str], i: int, time_duration_path: str, project_name: str,
                         num_outputs: int = 1) -> None:
        for j in range(num_outputs):
            for prompt_key, messages in messages_list.items():
                output_file_name = f"{i}{j}_{branch}_{class_name.split('.')[-1]}_{prompt_key}"
                self._process_single_prompt(messages, test_template, output_path, branch, class_name, imports, i, j, time_duration_path, project_name, output_file_name, prompt_key)

    def _process_single_prompt(self, messages: List[Dict[str, str]], test_template: str, output_path: str, branch: str,
                               class_name: str, imports: List[str], i: int, j: int, time_duration_path: str,
                               project_name: str, output_file_name: str, prompt_key: str) -> None:
        try:
            logging.debug("Processing output %d%d for prompt key '%s' in branch \"%s\"", i, j, prompt_key, branch)
            output = self.api.generate_output(messages)
            response = output.get("response", "Response not found.")
            total_duration = int(output.get("total_duration", self.api.timeout_seconds))
            self.save_output(test_template, response, output_path, output_file_name)
        except Exception as e:
            logging.error("Error while processing output %d%d for prompt key '%s' in branch \"%s\": %s", i, j, prompt_key, branch, e)
        finally:
            self.record_output_duration(time_duration_path, output_path, class_name, output_file_name, total_duration, project_name)

        self.extract_individual_tests(output_path, test_template, class_name, imports, i, j, prompt_key, branch)
