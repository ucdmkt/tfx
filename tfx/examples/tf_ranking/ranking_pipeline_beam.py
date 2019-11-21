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

import absl
import os
from typing import List, Text
from tfx.components.evaluator.component import Evaluator
from tfx.components.example_gen.import_example_gen.component import ImportExampleGen
from tfx.orchestration import metadata
from tfx.orchestration import pipeline
from tfx.orchestration.beam import beam_dag_runner
from tfx.proto import example_gen_pb2
from tfx.utils import dsl_utils

_pipeline_name = 'ranking_pipeline_beam'

_input_bucket = 'gs://tfx-kfp-ltr-bucket'
_output_bucket = 'gs://tfx-kfp-ltr-bucket'
_tfx_root = os.path.join(_output_bucket, 'tfx')
_pipeline_root = os.path.join(_tfx_root, _pipeline_name)

_data_root = os.path.join(_input_bucket, 'data/')

_project_id = 'tfx-kfp-learn-to-rank'
_gcp_region = 'us-central1'

_metadata_path = os.path.join(
    os.environ['HOME'], 'tfx', 'metadata', _pipeline_name, 'metadata.db')

_beam_pipeline_args = ['--runner=DirectRunner']

def _create_pipeline(
    pipeline_name: Text,
    pipeline_root: Text,
    data_root: Text,
    metadata_path: Text,
    beam_pipeline_args: List[Text],
) -> pipeline.Pipeline:
  """Implements a learn-to-rank pipeline with TFX and Kubeflow Pipelines."""

  # Brings data into the pipeline. It assumes ELWC is already materialized.
  example_gen = ImportExampleGen(
      input=dsl_utils.external_input(data_root),
      # Due to https://github.com/tensorflow/tfx/issues/956), explicit
      # input_config is necessary when data to ImportExampleGen is in GCS.
      input_config=example_gen_pb2.Input(
          splits=[
              example_gen_pb2.Input.Split(name='all', pattern='*.tfrecord'),
          ]
      )
  )

  return pipeline.Pipeline(
      pipeline_name=pipeline_name,
      pipeline_root=pipeline_root,
      components=[example_gen],
      metadata_connection_config=metadata.sqlite_metadata_connection_config(
          metadata_path),
      beam_pipeline_args=beam_pipeline_args,
  )


if __name__ == '__main__':
  absl.logging.set_verbosity(absl.logging.INFO)

  beam_dag_runner.BeamDagRunner().run(
      _create_pipeline(
          pipeline_name=_pipeline_name,
          pipeline_root=_pipeline_root,
          data_root=_data_root,
          metadata_path=_metadata_path,
          beam_pipeline_args=_beam_pipeline_args,
      ))
