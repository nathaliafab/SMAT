import json
from abc import ABC, abstractmethod
import logging
from os import makedirs, path
from typing import TypeVar, Generic

from nimrod.output_generation.output_generator_context import OutputGeneratorContext
from nimrod.tests.utils import get_base_output_path

T = TypeVar("T")


class OutputGenerator(ABC, Generic[T]):
    parent_dir = path.dirname(get_base_output_path())
    REPORTS_DIRECTORY = path.join(parent_dir, "reports")

    def __init__(self, report_name: str) -> None:
        super().__init__()
        makedirs(self.REPORTS_DIRECTORY, exist_ok=True)
        self._report_name = report_name + ".json"

    @abstractmethod
    def _generate_report_data(self, context: OutputGeneratorContext) -> T:
        pass

    def write_report(self, context: OutputGeneratorContext) -> None:
        logging.info(f"Starting generation of {self._report_name} report")
        file_path = path.join(self.REPORTS_DIRECTORY, self._report_name)

        logging.info(f"Starting data processing of {self._report_name} report")
        new_data = self._generate_report_data(context)
        logging.info(f"Finished data processing of {self._report_name} report")

        existing_data = self._load_existing_data(file_path)

        if not isinstance(existing_data, list):
            existing_data = [existing_data] if existing_data else []
        existing_data.append(new_data)

        self._write_json(file_path, existing_data)
        logging.info(f"Finished generation of {self._report_name} report")

    def _load_existing_data(self, file_path: str):
        if not path.exists(file_path):
            return []
        try:
            with open(file_path, "r") as read_file:
                return json.load(read_file)
        except json.JSONDecodeError:
            return []

    def _write_json(self, file_path: str, data) -> None:
        with open(file_path, "w") as write_file:
            json.dump(data, write_file, indent=4)
