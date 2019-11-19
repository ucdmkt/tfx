# Lint as: python2, python3
# Copyright 2019 Google LLC. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Chicago Taxi example using TFX DSL on Kubeflow with Google Cloud services."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
from typing import List, Text
from tfx.components.evaluator.component import Evaluator
from tfx.components.example_gen.import_example_gen.component import ImportExampleGen
from tfx.orchestration import pipeline
from tfx.orchestration.kubeflow import kubeflow_dag_runner
from tfx.utils import dsl_utils

_pipeline_name = 'ranking_pipeline_kubeflow_gcp'

_input_bucket = 'gs://tfx-kfp-ltr-bucket'
_output_bucket = 'gs://tfx-kfp-ltr-bucket'
_tfx_root = os.path.join(_output_bucket, 'tfx')
_pipeline_root = os.path.join(_tfx_root, _pipeline_name)

_data_root = os.path.join(_input_bucket, 'data')

_project_id = 'tfx-kfp-learn-to-rank'
_gcp_region = 'us-central1'

# Beam args to run data processing on DataflowRunner.
_beam_pipeline_args = [
    '--runner=DataflowRunner',
    '--experiments=shuffle_mode=auto',
    '--project=' + _project_id,
    '--temp_location=' + os.path.join(_output_bucket, 'tmp'),
    '--region=' + _gcp_region,
]

def _create_pipeline(
    pipeline_name: Text,
    pipeline_root: Text,
    data_root: Text,
    beam_pipeline_args: List[Text],
) -> pipeline.Pipeline:
  """Implements a learn-to-rank pipeline with TFX and Kubeflow Pipelines."""

  # Brings data into the pipeline or otherwise joins/converts training data.
  example_gen = ImportExampleGen(input=dsl_utils.external_input(data_root))

  return pipeline.Pipeline(
      pipeline_name=pipeline_name,
      pipeline_root=pipeline_root,
      components=[example_gen],
      beam_pipeline_args=beam_pipeline_args,
  )


if __name__ == '__main__':
  metadata_config = kubeflow_dag_runner.get_default_kubeflow_metadata_config()

  runner_config = kubeflow_dag_runner.KubeflowDagRunnerConfig(
      kubeflow_metadata_config=metadata_config,
  )

  kubeflow_dag_runner.KubeflowDagRunner(config=runner_config).run(
      _create_pipeline(
          pipeline_name=_pipeline_name,
          pipeline_root=_pipeline_root,
          data_root=_data_root,
          beam_pipeline_args=_beam_pipeline_args,
      ))
