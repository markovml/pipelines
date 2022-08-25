# Copyright 2021 The Kubeflow Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for kfp.components.executor."""

import json
import os
import tempfile
from typing import Callable, Dict, List, NamedTuple, Optional
import unittest

from absl.testing import parameterized
from kfp.components import executor
from kfp.components.task_final_status import PipelineTaskFinalStatus
from kfp.components.types import artifact_types
from kfp.components.types.artifact_types import Artifact
from kfp.components.types.artifact_types import Dataset
from kfp.components.types.artifact_types import Metrics
from kfp.components.types.artifact_types import Model
from kfp.components.types.type_annotations import Input
from kfp.components.types.type_annotations import InputPath
from kfp.components.types.type_annotations import Output
from kfp.components.types.type_annotations import OutputPath


class ExecutorTest(unittest.TestCase):

    @classmethod
    def setUp(cls):
        cls.maxDiff = None
        cls._test_dir = tempfile.mkdtemp()
        artifact_types._GCS_LOCAL_MOUNT_PREFIX = cls._test_dir + '/'
        artifact_types._MINIO_LOCAL_MOUNT_PREFIX = cls._test_dir + '/minio/'
        artifact_types._S3_LOCAL_MOUNT_PREFIX = cls._test_dir + '/s3/'

    def execute_and_load_output_metadata(
            self, func: Callable, executor_input: str) -> executor.Executor:
        executor_input_dict = json.loads(executor_input %
                                         {'test_dir': self._test_dir})

        executor.Executor(
            executor_input=executor_input_dict,
            function_to_execute=func).execute()
        with open(os.path.join(self._test_dir, 'output_metadata.json'),
                  'r') as f:
            return json.loads(f.read())

    def test_input_parameter(self):
        executor_input = """\
        {
          "inputs": {
            "parameterValues": {
              "input_parameter": "Hello, KFP"
            }
          },
          "outputs": {
            "parameters": {
              "output": {
                "outputFile": "gs://some-bucket/output"
              }
            },
            "outputFile": "%(test_dir)s/output_metadata.json"
          }
        }
        """

        def test_func(input_parameter: str) -> str:
            self.assertEqual(input_parameter, 'Hello, KFP')
            return input_parameter

        output_metadata = self.execute_and_load_output_metadata(
            test_func, executor_input)
        self.assertEqual({'parameterValues': {
            'Output': 'Hello, KFP'
        }}, output_metadata)

    def test_input_artifact_custom_type(self):
        executor_input = """\
        {
          "inputs": {
            "parameterValues": {
            },
            "artifacts": {
              "input_artifact_one": {
                "artifacts": [
                  {
                    "metadata": {},
                    "name": "input_artifact_one",
                    "type": {
                      "schemaTitle": "google.VertexDataset"
                    },
                    "uri": "gs://some-bucket/input_artifact_one"
                  }
                ]
              }
            }
          },
          "outputs": {
            "outputFile": "%(test_dir)s/output_metadata.json"
          }
        }
        """

        class VertexDataset:
            TYPE_NAME = 'google.VertexDataset'

            def __init__(self, name: str, uri: str, metadata: dict) -> None:
                self.name = name
                self.uri = uri
                self.metadata = metadata

            @property
            def path(self) -> str:
                return self.uri.replace('gs://', '/gcs/')

        def test_func(input_artifact_one: Input[VertexDataset]):
            self.assertEqual(input_artifact_one.uri,
                             'gs://some-bucket/input_artifact_one')
            self.assertEqual(
                input_artifact_one.path,
                os.path.join(self._test_dir,
                             '/gcs/some-bucket/input_artifact_one'))
            self.assertEqual(input_artifact_one.name, 'input_artifact_one')
            self.assertIsInstance(input_artifact_one, VertexDataset)

        self.execute_and_load_output_metadata(test_func, executor_input)

    def test_input_artifact(self):
        executor_input = """\
        {
          "inputs": {
            "parameterValues": {
            },
            "artifacts": {
              "input_artifact_one": {
                "artifacts": [
                  {
                    "metadata": {},
                    "name": "input_artifact_one",
                    "type": {
                      "schemaTitle": "google.VertexDataset"
                    },
                    "uri": "gs://some-bucket/input_artifact_one"
                  }
                ]
              }
            }
          },
          "outputs": {
            "outputFile": "%(test_dir)s/output_metadata.json"
          }
        }
        """

        def test_func(input_artifact_one: Input[Dataset]):
            self.assertEqual(input_artifact_one.uri,
                             'gs://some-bucket/input_artifact_one')
            self.assertEqual(
                input_artifact_one.path,
                os.path.join(self._test_dir, 'some-bucket/input_artifact_one'))
            self.assertEqual(input_artifact_one.name, 'input_artifact_one')
            self.assertIsInstance(input_artifact_one, Dataset)

        self.execute_and_load_output_metadata(test_func, executor_input)

    def test_output_artifact(self):
        executor_input = """\
        {
          "inputs": {
          },
          "outputs": {
            "artifacts": {
              "output_artifact_one": {
                "artifacts": [
                  {
                    "metadata": {},
                    "name": "output_artifact_one",
                    "type": {
                      "schemaTitle": "system.Model"
                    },
                    "uri": "gs://some-bucket/output_artifact_one"
                  }
                ]
              }
            },
            "outputFile": "%(test_dir)s/output_metadata.json"
          }
        }
        """

        def test_func(output_artifact_one: Output[Model]):
            self.assertEqual(output_artifact_one.uri,
                             'gs://some-bucket/output_artifact_one')

            self.assertEqual(
                output_artifact_one.path,
                os.path.join(self._test_dir, 'some-bucket/output_artifact_one'))
            self.assertEqual(output_artifact_one.name, 'output_artifact_one')
            self.assertIsInstance(output_artifact_one, Model)

        self.execute_and_load_output_metadata(test_func, executor_input)

    def test_output_parameter(self):
        executor_input = """\
        {
          "inputs": {
          },
          "outputs": {
            "parameters": {
              "output_parameter_path": {
                "outputFile": "%(test_dir)s/gcs/some-bucket/some_task/nested/output_parameter"
              }
            },
            "outputFile": "%(test_dir)s/output_metadata.json"
          }
        }
        """

        def test_func(output_parameter_path: OutputPath(str)):
            # Test that output parameters just use the passed in filename.
            self.assertEqual(
                output_parameter_path, self._test_dir +
                '/gcs/some-bucket/some_task/nested/output_parameter')
            with open(output_parameter_path, 'w') as f:
                f.write('Hello, World!')

        self.execute_and_load_output_metadata(test_func, executor_input)

    def test_input_path_artifact(self):
        executor_input = """\
      {
        "inputs": {
          "artifacts": {
            "input_artifact_one_path": {
              "artifacts": [
                {
                  "metadata": {},
                  "name": "input_artifact_one",
                  "type": {
                    "schemaTitle": "system.Dataset"
                  },
                  "uri": "gs://some-bucket/input_artifact_one"
                }
              ]
            }
          }
        },
        "outputs": {
          "outputFile": "%(test_dir)s/output_metadata.json"
        }
      }
      """

        def test_func(input_artifact_one_path: InputPath('Dataset')):
            self.assertEqual(
                input_artifact_one_path,
                os.path.join(self._test_dir, 'some-bucket/input_artifact_one'))

        self.execute_and_load_output_metadata(test_func, executor_input)

    def test_output_path_artifact(self):
        executor_input = """\
      {
        "inputs": {
        },
        "outputs": {
          "artifacts": {
            "output_artifact_one_path": {
              "artifacts": [
                {
                  "metadata": {},
                  "name": "output_artifact_one",
                  "type": {
                    "schemaTitle": "system.Model"
                  },
                  "uri": "gs://some-bucket/output_artifact_one"
                }
              ]
            }
          },
          "outputFile": "%(test_dir)s/output_metadata.json"
        }
      }
      """

        def test_func(output_artifact_one_path: OutputPath('Model')):
            self.assertEqual(
                output_artifact_one_path,
                os.path.join(self._test_dir, 'some-bucket/output_artifact_one'))

        self.execute_and_load_output_metadata(test_func, executor_input)

    def test_output_metadata(self):
        executor_input = """\
      {
        "inputs": {
        },
        "outputs": {
          "artifacts": {
            "output_artifact_two": {
              "artifacts": [
                {
                  "metadata": {},
                  "name": "output_artifact_two",
                  "type": {
                    "schemaTitle": "system.Metrics"
                  },
                  "uri": "gs://some-bucket/output_artifact_two"
                }
              ]
            }
          },
          "outputFile": "%(test_dir)s/output_metadata.json"
        }
      }
      """

        def test_func(output_artifact_two: Output[Metrics]):
            output_artifact_two.metadata['key_1'] = 'value_1'
            output_artifact_two.metadata['key_2'] = 2
            output_artifact_two.uri = 'new-uri'

            # log_metric works here since the schema is specified as Metrics.
            output_artifact_two.log_metric('metric', 0.9)

        output_metadata = self.execute_and_load_output_metadata(
            test_func, executor_input)

        self.assertDictEqual(
            output_metadata, {
                'artifacts': {
                    'output_artifact_two': {
                        'artifacts': [{
                            'name': 'output_artifact_two',
                            'uri': 'new-uri',
                            'metadata': {
                                'key_1': 'value_1',
                                'key_2': 2,
                                'metric': 0.9
                            }
                        }]
                    }
                }
            })

    def test_function_string_output(self):
        executor_input = """\
    {
      "inputs": {
        "parameterValues": {
          "first_message": "Hello",
          "second_message": ", ",
          "third_message": "World"
        }
      },
      "outputs": {
        "parameters": {
          "output": {
            "outputFile": "gs://some-bucket/output"
          }
        },
        "outputFile": "%(test_dir)s/output_metadata.json"
      }
    }
    """

        def test_func(
            first_message: str,
            second_message: str,
            third_message: str,
        ) -> str:
            return first_message + second_message + third_message

        output_metadata = self.execute_and_load_output_metadata(
            test_func, executor_input)
        self.assertDictEqual(output_metadata, {
            'parameterValues': {
                'Output': 'Hello, World'
            },
        })

    def test_function_with_int_output(self):
        executor_input = """\
    {
      "inputs": {
        "parameterValues": {
          "first": 40,
          "second": 2
        }
      },
      "outputs": {
        "parameters": {
          "output": {
            "outputFile": "gs://some-bucket/output"
          }
        },
        "outputFile": "%(test_dir)s/output_metadata.json"
      }
    }
    """

        def test_func(first: int, second: int) -> int:
            return first + second

        output_metadata = self.execute_and_load_output_metadata(
            test_func, executor_input)
        self.assertDictEqual(output_metadata, {
            'parameterValues': {
                'Output': 42
            },
        })

    def test_function_with_float_output(self):
        executor_input = """\
    {
      "inputs": {
        "parameterValues": {
          "first": 0.0,
          "second": 1.2
        }
      },
      "outputs": {
        "parameters": {
          "output": {
            "outputFile": "gs://some-bucket/output"
          }
        },
        "outputFile": "%(test_dir)s/output_metadata.json"
      }
    }
    """

        def test_func(first: float, second: float) -> float:
            return first + second

        output_metadata = self.execute_and_load_output_metadata(
            test_func, executor_input)

        self.assertDictEqual(output_metadata, {
            'parameterValues': {
                'Output': 1.2
            },
        })

    def test_function_with_list_output(self):
        executor_input = """\
    {
      "inputs": {
        "parameterValues": {
          "first": 40,
          "second": 2
        }
      },
      "outputs": {
        "parameters": {
          "output": {
            "outputFile": "gs://some-bucket/output"
          }
        },
        "outputFile": "%(test_dir)s/output_metadata.json"
      }
    }
    """

        def test_func(first: int, second: int) -> List:
            return [first, second]

        output_metadata = self.execute_and_load_output_metadata(
            test_func, executor_input)

        self.assertDictEqual(output_metadata, {
            'parameterValues': {
                'Output': [40, 2]
            },
        })

    def test_function_with_dict_output(self):
        executor_input = """\
    {
      "inputs": {
        "parameterValues": {
          "first": 40,
          "second": 2
        }
      },
      "outputs": {
        "parameters": {
          "output": {
            "outputFile": "gs://some-bucket/output"
          }
        },
        "outputFile": "%(test_dir)s/output_metadata.json"
      }
    }
    """

        def test_func(first: int, second: int) -> Dict:
            return {'first': first, 'second': second}

        output_metadata = self.execute_and_load_output_metadata(
            test_func, executor_input)

        self.assertDictEqual(output_metadata, {
            'parameterValues': {
                'Output': {
                    'first': 40,
                    'second': 2
                }
            },
        })

    def test_function_with_typed_list_output(self):
        executor_input = """\
    {
      "inputs": {
        "parameterValues": {
          "first": 40,
          "second": 2
        }
      },
      "outputs": {
        "parameters": {
          "output": {
            "outputFile": "gs://some-bucket/output"
          }
        },
        "outputFile": "%(test_dir)s/output_metadata.json"
      }
    }
    """

        def test_func(first: int, second: int) -> List[int]:
            return [first, second]

        output_metadata = self.execute_and_load_output_metadata(
            test_func, executor_input)

        self.assertDictEqual(output_metadata, {
            'parameterValues': {
                'Output': [40, 2]
            },
        })

    def test_function_with_typed_dict_output(self):
        executor_input = """\
    {
      "inputs": {
        "parameterValues": {
          "first": 40,
          "second": 2
        }
      },
      "outputs": {
        "parameters": {
          "output": {
            "outputFile": "gs://some-bucket/output"
          }
        },
        "outputFile": "%(test_dir)s/output_metadata.json"
      }
    }
    """

        def test_func(first: int, second: int) -> Dict[str, int]:
            return {'first': first, 'second': second}

        output_metadata = self.execute_and_load_output_metadata(
            test_func, executor_input)

        self.assertDictEqual(output_metadata, {
            'parameterValues': {
                'Output': {
                    'first': 40,
                    'second': 2
                }
            },
        })

    def test_artifact_output(self):
        executor_input = """\
    {
      "inputs": {
        "parameterValues": {
          "first":  "Hello",
          "second": "World"
        }
      },
      "outputs": {
        "artifacts": {
          "output": {
            "artifacts": [
              {
                "name": "output",
                "type": {
                  "schemaTitle": "system.Artifact"
                },
                "uri": "gs://some-bucket/output"
              }
            ]
          }
        },
        "outputFile": "%(test_dir)s/output_metadata.json"
      }
    }
    """

        def test_func(first: str, second: str, output: Output[Artifact]) -> str:
            with open(output.path, 'w') as f:
                f.write('artifact output')
            return first + ', ' + second

        output_metadata = self.execute_and_load_output_metadata(
            test_func, executor_input)

        self.assertDictEqual(
            output_metadata, {
                'artifacts': {
                    'output': {
                        'artifacts': [{
                            'metadata': {},
                            'name': 'output',
                            'uri': 'gs://some-bucket/output'
                        }]
                    }
                },
                'parameterValues': {
                    'Output': 'Hello, World'
                }
            })

        with open(os.path.join(self._test_dir, 'some-bucket/output'), 'r') as f:
            artifact_payload = f.read()
        self.assertEqual(artifact_payload, 'artifact output')

    def test_named_tuple_output(self):
        executor_input = """\
        {
          "outputs": {
            "artifacts": {
              "output_dataset": {
                "artifacts": [
                  {
                    "name": "output_dataset",
                    "type": {
                      "schemaTitle": "system.Dataset"
                    },
                    "uri": "gs://some-bucket/output_dataset"
                  }
                ]
              }
            },
            "parameters": {
              "output_int": {
                "outputFile": "gs://some-bucket/output_int"
              },
              "output_string": {
                "outputFile": "gs://some-bucket/output_string"
              }
            },
            "outputFile": "%(test_dir)s/output_metadata.json"
          }
        }
        """

        # Functions returning named tuples should work.
        def func_returning_named_tuple() -> NamedTuple('Outputs', [
            ('output_dataset', Dataset),
            ('output_int', int),
            ('output_string', str),
        ]):
            from collections import namedtuple
            output = namedtuple(
                'Outputs', ['output_dataset', 'output_int', 'output_string'])
            return output('Dataset contents', 101, 'Some output string')

        # Functions returning plain tuples should work too.
        def func_returning_plain_tuple() -> NamedTuple('Outputs', [
            ('output_dataset', Dataset),
            ('output_int', int),
            ('output_string', str),
        ]):
            return ('Dataset contents', 101, 'Some output string')

        for test_func in [
                func_returning_named_tuple, func_returning_plain_tuple
        ]:
            output_metadata = self.execute_and_load_output_metadata(
                test_func, executor_input)

            self.assertDictEqual(
                output_metadata, {
                    'artifacts': {
                        'output_dataset': {
                            'artifacts': [{
                                'metadata': {},
                                'name': 'output_dataset',
                                'uri': 'gs://some-bucket/output_dataset'
                            }]
                        }
                    },
                    'parameterValues': {
                        'output_int': 101,
                        'output_string': 'Some output string'
                    },
                })

            with open(
                    os.path.join(self._test_dir, 'some-bucket/output_dataset'),
                    'r') as f:
                artifact_payload = f.read()
            self.assertEqual(artifact_payload, 'Dataset contents')

    def test_function_with_optional_inputs(self):
        executor_input = """\
        {
          "inputs": {
            "parameterValues": {
              "first_message": "Hello",
              "second_message": "World"
            }
          },
          "outputs": {
            "parameters": {
              "output": {
                "outputFile": "gs://some-bucket/output"
              }
            },
            "outputFile": "%(test_dir)s/output_metadata.json"
          }
        }
        """

        def test_func(
            first_message: str = 'default value',
            second_message: Optional[str] = None,
            third_message: Optional[str] = None,
            fourth_argument: str = 'abc',
            fifth_argument: int = 100,
            sixth_argument: float = 1.23,
            seventh_argument: bool = True,
            eighth_argument: list = [1, 2],
            ninth_argument: dict = {'a': 1},
        ) -> str:
            return (f'{first_message} ({type(first_message)}), '
                    f'{second_message} ({type(second_message)}), '
                    f'{third_message} ({type(third_message)}), '
                    f'{fourth_argument} ({type(fourth_argument)}), '
                    f'{fifth_argument} ({type(fifth_argument)}), '
                    f'{sixth_argument} ({type(sixth_argument)}), '
                    f'{seventh_argument} ({type(seventh_argument)}), '
                    f'{eighth_argument} ({type(eighth_argument)}), '
                    f'{ninth_argument} ({type(ninth_argument)}).')

        output_metadata = self.execute_and_load_output_metadata(
            test_func, executor_input)

        self.assertDictEqual(
            output_metadata, {
                'parameterValues': {
                    'Output': "Hello (<class 'str'>), "
                              "World (<class 'str'>), "
                              "None (<class 'NoneType'>), "
                              "abc (<class 'str'>), "
                              "100 (<class 'int'>), "
                              "1.23 (<class 'float'>), "
                              "True (<class 'bool'>), "
                              "[1, 2] (<class 'list'>), "
                              "{'a': 1} (<class 'dict'>)."
                },
            })

    def test_function_with_pipeline_task_final_status(self):
        executor_input = """\
    {
      "inputs": {
        "parameterValues": {
          "status": {"error":{"code":9,"message":"The DAG failed because some tasks failed. The failed tasks are: [fail-op]."},"pipelineJobResourceName":"projects/123/locations/us-central1/pipelineJobs/pipeline-456", "pipelineTaskName": "upstream-task", "state":"FAILED"}
        }
      },
      "outputs": {
        "parameters": {
          "output": {
            "outputFile": "gs://some-bucket/output"
          }
        },
        "outputFile": "%(test_dir)s/output_metadata.json"
      }
    }
    """

        def test_func(status: PipelineTaskFinalStatus) -> str:
            return (f'Pipeline status: {status.state}\n'
                    f'Job resource name: {status.pipeline_job_resource_name}\n'
                    f'Pipeline task name: {status.pipeline_task_name}\n'
                    f'Error code: {status.error_code}\n'
                    f'Error message: {status.error_message}')

        output_metadata = self.execute_and_load_output_metadata(
            test_func, executor_input)

        self.assertDictEqual(
            output_metadata, {
                'parameterValues': {
                    'Output':
                        'Pipeline status: FAILED\n'
                        'Job resource name: projects/123/locations/us-central1/pipelineJobs/pipeline-456\n'
                        'Pipeline task name: upstream-task\n'
                        'Error code: 9\n'
                        'Error message: The DAG failed because some tasks failed. The failed tasks are: [fail-op].'
                },
            })


class VertexDataset:
    schema_title = 'google.VertexDataset'
    schema_version = '0.0.0'

    def __init__(self, name: str, uri: str, metadata: dict) -> None:
        self.name = name
        self.uri = uri
        self.metadata = metadata

    @property
    def path(self) -> str:
        return self.uri.replace('gs://', '/gcs/')


class TestDictToArtifact(parameterized.TestCase):

    @parameterized.parameters(
        {
            'runtime_artifact': {
                'metadata': {},
                'name': 'input_artifact_one',
                'type': {
                    'schemaTitle': 'system.Artifact'
                },
                'uri': 'gs://some-bucket/input_artifact_one'
            },
            'artifact_cls': artifact_types.Artifact,
            'expected_type': artifact_types.Artifact,
        },
        {
            'runtime_artifact': {
                'metadata': {},
                'name': 'input_artifact_one',
                'type': {
                    'schemaTitle': 'system.Model'
                },
                'uri': 'gs://some-bucket/input_artifact_one'
            },
            'artifact_cls': artifact_types.Model,
            'expected_type': artifact_types.Model,
        },
        {
            'runtime_artifact': {
                'metadata': {},
                'name': 'input_artifact_one',
                'type': {
                    'schemaTitle': 'system.Dataset'
                },
                'uri': 'gs://some-bucket/input_artifact_one'
            },
            'artifact_cls': artifact_types.Dataset,
            'expected_type': artifact_types.Dataset,
        },
        {
            'runtime_artifact': {
                'metadata': {},
                'name': 'input_artifact_one',
                'type': {
                    'schemaTitle': 'system.Metrics'
                },
                'uri': 'gs://some-bucket/input_artifact_one'
            },
            'artifact_cls': artifact_types.Metrics,
            'expected_type': artifact_types.Metrics,
        },
        {
            'runtime_artifact': {
                'metadata': {},
                'name': 'input_artifact_one',
                'type': {
                    'schemaTitle': 'system.ClassificationMetrics'
                },
                'uri': 'gs://some-bucket/input_artifact_one'
            },
            'artifact_cls': artifact_types.ClassificationMetrics,
            'expected_type': artifact_types.ClassificationMetrics,
        },
        {
            'runtime_artifact': {
                'metadata': {},
                'name': 'input_artifact_one',
                'type': {
                    'schemaTitle': 'system.SlicedClassificationMetrics'
                },
                'uri': 'gs://some-bucket/input_artifact_one'
            },
            'artifact_cls': artifact_types.SlicedClassificationMetrics,
            'expected_type': artifact_types.SlicedClassificationMetrics,
        },
        {
            'runtime_artifact': {
                'metadata': {},
                'name': 'input_artifact_one',
                'type': {
                    'schemaTitle': 'system.HTML'
                },
                'uri': 'gs://some-bucket/input_artifact_one'
            },
            'artifact_cls': None,
            'expected_type': artifact_types.HTML,
        },
        {
            'runtime_artifact': {
                'metadata': {},
                'name': 'input_artifact_one',
                'type': {
                    'schemaTitle': 'system.Markdown'
                },
                'uri': 'gs://some-bucket/input_artifact_one'
            },
            'artifact_cls': None,
            'expected_type': artifact_types.Markdown,
        },
    )
    def test_dict_to_artifact_kfp_artifact(
        self,
        runtime_artifact,
        artifact_cls,
        expected_type,
    ):
        # with artifact_cls
        self.assertIsInstance(
            executor.create_artifact_instance(
                runtime_artifact, artifact_cls=artifact_cls), expected_type)

        # without artifact_cls
        self.assertIsInstance(
            executor.create_artifact_instance(runtime_artifact), expected_type)

    def test_dict_to_artifact_nonkfp_artifact(self):
        runtime_artifact = {
            'metadata': {},
            'name': 'input_artifact_one',
            'type': {
                'schemaTitle': 'google.VertexDataset'
            },
            'uri': 'gs://some-bucket/input_artifact_one'
        }
        # with artifact_cls
        self.assertIsInstance(
            executor.create_artifact_instance(
                runtime_artifact, artifact_cls=VertexDataset), VertexDataset)

        # without artifact_cls
        self.assertIsInstance(
            executor.create_artifact_instance(runtime_artifact),
            artifact_types.Artifact)


if __name__ == '__main__':
    unittest.main()
