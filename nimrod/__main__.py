import logging
from typing import Dict, List, Any
from nimrod.dynamic_analysis.behavior_change_checker import BehaviorChangeChecker
from nimrod.dynamic_analysis.criteria.first_semantic_conflict_criteria import FirstSemanticConflictCriteria
from nimrod.dynamic_analysis.criteria.second_semantic_conflict_criteria import SecondSemanticConflictCriteria
from nimrod.dynamic_analysis.main import DynamicAnalysis
from nimrod.core.merge_scenario_under_analysis import MergeScenarioUnderAnalysis
from nimrod.output_generation.behavior_change_output_generator import BehaviorChangeOutputGenerator
from nimrod.output_generation.output_generator import OutputGenerator
from nimrod.output_generation.semantic_conflicts_output_generator import SemanticConflictsOutputGenerator
from nimrod.output_generation.test_suites_output_generator import TestSuitesOutputGenerator
from nimrod.smat import SMAT
from nimrod.test_suite_generation.main import TestSuiteGeneration
from nimrod.tests.utils import setup_logging, get_config
from nimrod.test_suite_generation.generators.test_suite_generator import TestSuiteGenerator
from nimrod.test_suite_generation.generators.randoop_test_suite_generator import RandoopTestSuiteGenerator
from nimrod.test_suite_generation.generators.evosuite_differential_test_suite_generator import EvosuiteDifferentialTestSuiteGenerator
from nimrod.test_suite_generation.generators.evosuite_test_suite_generator import EvosuiteTestSuiteGenerator
from nimrod.test_suite_generation.generators.ollama_test_suite_generator import OllamaTestSuiteGenerator
from nimrod.test_suite_generation.generators.project_test_suite_generator import ProjectTestSuiteGenerator
from nimrod.test_suites_execution.main import TestSuitesExecution, TestSuiteExecutor
from nimrod.tools.bin import MOD_RANDOOP, RANDOOP
from nimrod.tools.java import Java
from nimrod.tools.jacoco import Jacoco
from nimrod.input_parsing.input_parser import CsvInputParser, JsonInputParser


def get_llm_test_suite_generators(config: Dict[str, Any]) -> List[TestSuiteGenerator]:
  """
  Creates test suite generators for all available LLM models configured in api_params.
  Each model gets its own generator instance to enable parallel processing and comparison.
  """
  generators: List[TestSuiteGenerator] = list()
  api_params = config.get('api_params', {})
  
  for model_key, model_config in api_params.items():
    # Create a generator for each configured model
    generator = OllamaTestSuiteGenerator(Java(), model_key, model_config)
    generators.append(generator)
    
  return generators


def get_test_suite_generators(config: Dict[str, str]) -> List[TestSuiteGenerator]:
  config_generators = config.get(
      'test_suite_generators', ['randoop', 'randoop-modified', 'evosuite', 'evosuite-differential', 'ollama', 'project'])
  generators: List[TestSuiteGenerator] = list()

  if 'randoop' in config_generators:
    generators.append(RandoopTestSuiteGenerator(Java(), RANDOOP, "RANDOOP"))
  if 'randoop-modified' in config_generators:
    generators.append(RandoopTestSuiteGenerator(
        Java(), MOD_RANDOOP, "RANDOOP_MODIFIED"))
  if 'evosuite' in config_generators:
    generators.append(EvosuiteTestSuiteGenerator(Java()))
  if 'evosuite-differential' in config_generators:
    generators.append(EvosuiteDifferentialTestSuiteGenerator(Java()))
  if 'ollama' in config_generators:
    # Create one generator for each configured model
    generators.extend(get_llm_test_suite_generators(config))
  if 'project' in config_generators:
    generators.append(ProjectTestSuiteGenerator(Java()))

  return generators


def get_output_generators(config: Dict[str, str]) -> List[OutputGenerator]:
  config_generators = config.get(
      'output_generators', ['behavior_changes', 'semantic_conflicts', 'test_suites'])
  generators: List[OutputGenerator] = list()

  if 'behavior_changes' in config_generators:
    generators.append(BehaviorChangeOutputGenerator())
  if 'semantic_conflicts' in config_generators:
    generators.append(SemanticConflictsOutputGenerator(
        TestSuitesExecution(TestSuiteExecutor(Java(), Jacoco(Java())))))
  if 'test_suites' in config_generators:
    generators.append(TestSuitesOutputGenerator())

  return generators


def parse_scenarios_from_input(config: Dict[str, str]) -> List[MergeScenarioUnderAnalysis]:
    json_input = config.get('input_path', "")
    csv_input_path = config.get('path_hash_csv', "")

    if json_input != "":
        return JsonInputParser().parse_input(json_input)
    elif csv_input_path != "":
        logging.warning(
            'DEPRECATED: Providing input data with `path_hash_csv` is deprecated and will be removed in future versions of SMAT. Use `input_path` instead.')
        return CsvInputParser().parse_input(csv_input_path)
    else:
        logging.fatal('No input file provided')
        exit(1)


def main():
  setup_logging()
  config = get_config()
  test_suite_generators = get_test_suite_generators(config)
  test_suite_generation = TestSuiteGeneration(test_suite_generators)
  test_suites_execution = TestSuitesExecution(
      TestSuiteExecutor(Java(), Jacoco(Java())))
  dynamic_analysis = DynamicAnalysis([
      FirstSemanticConflictCriteria(),
      SecondSemanticConflictCriteria()
  ], BehaviorChangeChecker())
  output_generators = get_output_generators(config)

  smat = SMAT(test_suite_generation, test_suites_execution, dynamic_analysis, output_generators)
  scenarios = parse_scenarios_from_input(config)

  for scenario in scenarios:
    if scenario.run_analysis:
      smat.run_tool_for_semmantic_conflict_detection(scenario)
    else:
      logging.info(f"Skipping tool execution for project {scenario.project_name}")


if __name__ == '__main__':
  main()
