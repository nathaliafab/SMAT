import logging
import os
import json
import shutil
from typing import Dict

PATH = os.path.dirname(os.path.abspath(__file__))


def get_config() -> "Dict[str, str]":
    config: "Dict[str, str]" = dict()

    with open(os.path.join(PATH, os.sep.join(['env-config.json'])), 'r') as j:
        config = json.loads(j.read())

    return config


def calculator_project_dir():
    return os.path.join(PATH, 'example')


def calculator_package():
    return 'br.ufal.ic.easy'


def calculator_src_dir():
    return os.path.join(calculator_project_dir(), 'src', 'main', 'java')


def calculator_package_dir():
    return os.path.join(calculator_src_dir(), 'br', 'ufal', 'ic', 'easy')


def calculator_java_file():
    return os.path.join(calculator_package_dir(), 'Calculator.java')


def calculator_operation_java_file():
    return os.path.join(calculator_package_dir(), 'operations',
                        'Operation.java')


def calculator_target_dir():
    return os.path.join(calculator_project_dir(), 'target')


def calculator_clean_project():
    target_dir = calculator_target_dir()

    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)


def calculator_mutants_dir():
    return os.path.join(calculator_project_dir(), 'mutants')


def calculator_mutants_log():
    return os.path.join(calculator_mutants_dir(), 'mutation_log')


def calculator_sum_original():
    return os.path.join(calculator_package_dir(), 'operations',
                        'Sum.java')


def calculator_src_aor_1():
    return os.path.join(calculator_mutants_dir(), 'AOR_1')


def calculator_sum_aor_1():
    return os.path.join(calculator_src_aor_1(), 'br', 'ufal', 'ic', 'easy',
                        'operations', 'Sum.java')


def setup_logging():
    config = get_config()
    config_level = config.get('logger_level', 'INFO').upper()
    level = logging._nameToLevel.get(config_level, logging.INFO)

    logger = logging.getLogger()
    logger.setLevel(level)

    if logger.hasHandlers():
        logger.handlers.clear()

    modules_to_ignore = [
        'mlc_chat.support.auto_device',
        'mlc_chat.support',
        'mlc_chat',
        'mlc_chat.support.config',
        'mlc_chat.chat_module',
        'mlc_chat.serve.engine',
        'mlc_chat.serve',
        'auto_device',
        'chat_module',
        'model_metadata'
    ]

    for module in modules_to_ignore:
        mod_logger = logging.getLogger(module)
        mod_logger.setLevel(logging.ERROR)
        mod_logger.propagate = False

    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s %(filename)s:%(lineno)d: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    file_handler = logging.FileHandler('logfile.log', mode='a')
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

def get_base_output_path() -> str:
    current_dir = os.getcwd()
    base_dir = current_dir.replace("/nimrod/proj", "") if "/nimrod/proj" in current_dir else current_dir
    return os.path.join(base_dir, "output-test-dest", "projects")
