# TensorFlow Data Validation: Checking and analyzing your data

Once your data is in a TFX pipeline, you can use TFX components to analyze
and transform it. You can use these tools even before you train a model.

There are many reasons to analyze and transform your data:

*   To find problems in your data. Common problems include:
    *   Missing data, such as features with empty values.
    *   Labels treated as features, so that your model gets to peek at the right
        answer during training.
    *   Features with values outside the range you expect.
    *   Data anomalies.
*   To engineer more effective feature sets. For example, you can identify:
    *   Especially informative features.
    *   Redundant features.
    *   Features that vary so widely in scale that they may slow learning.
    *   Features with little or no unique predictive information.

TFX tools can both help find data bugs, and help with feature engineering.

## TensorFlow Data Validation

*   [Overview](#tfdv-overview)
*   [Schema Based Example Validation](#tfdv-schema-based-example-validation)
*   [Training-Serving Skew Detection](#tfdv-training-serving-skew-detection)
*   [Drift Detection](#tfdv-drift-detection)

### Overview {#tfdv-overview}

TensorFlow Data Validation identifies anomalies in training and serving data,
and can automatically create a schema by examining the data. The component can
be configured to detect different classes of anomalies in the data. It can

1.  Perform validity checks by comparing data statistics against a schema that
    codifies expectations of the user.
1.  Detect training-serving skew by comparing examples in training and serving
    data.
1.  Detect data drift by looking at a series of data.

We document each of these functionalities independently:

*   [Schema Based Example Validation](#tfdv-schema-based-example-validation)
*   [Training-Serving Skew Detection](#tfdv-training-serving-skew-detection)
*   [Drift Detection](#tfdv-drift-detection)

### Schema Based Example Validation {#tfdv-schema-based-example-validation}

TensorFlow Data Validation identifies any anomalies in the input data by
comparing data statistics against a schema. The schema codifies properties
which the input data is expected to satisfy, such as data types or categorical
values, and can be modified or replaced by the user.

#### Advanced Schema Features

This section covers more advanced schema configuration that can help with
special setups.

##### Sparse Features

Encoding sparse features in Examples usually introduces multiple Features that
are expected to have the same valency for all Examples. For example the sparse
feature:
<pre><code>
WeightedCategories = [('CategoryA', 0.3), ('CategoryX', 0.7)]
</code></pre>
would be encoded using separate Features for index and value:
<pre><code>
WeightedCategoriesIndex = ['CategoryA', 'CategoryX']
WeightedCategoriesValue = [0.3, 0.7]
</code></pre>
with the restriction that the valency of the index and value feature should
match for all Examples. This restriction can be made explicit in the schema by
defining a sparse_feature:
<pre><code class="lang-proto">
sparse_feature {
  name: 'WeightedCategories'
  index_feature { name: 'WeightedCategoriesIndex' }
  value_feature { name: 'WeightedCategoriesValue' }
}
</code></pre>

The sparse feature definition requires one or more index and one value feature
which refer to features that exist in the schema. Explicitly defining
sparse features enables TFDV to check that the valencies of all referred
features match.

Some use cases introduce similar valency restrictions between Features, but do
not necessarily encode a sparse feature. Using sparse feature should unblock
you, but is not ideal.

##### Schema Environments

By default validations assume that all Examples in a pipeline adhere to a single
schema. In some cases introducing slight schema variations is necessary, for
instance features used as labels are required during training (and should be
validated), but are missing during serving. Environments can be used to express
such requirements, in particular `default_environment()`, `in_environment()`,
`not_in_environment()`.

For example, assume a feature named 'LABEL' is required for training, but is
expected to be missing from serving. This can be expressed by:

*   Define two distinct environments in the schema: ["SERVING", "TRAINING"] and
    associate 'LABEL' only with environment "TRAINING".
*   Associate the training data with environment "TRAINING" and the
    serving data with environment "SERVING".

##### Schema Generation

The input data schema is specified as an instance of the TensorFlow
[Schema](
https://github.com/tensorflow/metadata/blob/master/tensorflow_metadata/proto/v0/schema.proto).

Instead of constructing a schema manually from scratch, a developer can rely on
TensorFlow Data Validation's automatic schema construction. Specifically,
TensorFlow Data Validation automatically constructs an initial schema based on
statistics computed over training data available in the pipeline. Users can
simply review this autogenerated schema, modify it as needed, check it into a
version control system, and push it explicitly into the pipeline for further
validation.

TFDV includes `infer_schema()` to generate a schema automatically.  For example:

```python
schema = tfdv.infer_schema(statistics=train_stats)
tfdv.display_schema(schema=schema)
```

This triggers an automatic schema generation based on the following rules:

*   If a schema has already been auto-generated then it is used as is.

*   Otherwise, TensorFlow Data Validation examines the available data statistics
and computes a suitable schema for the data.

_Note: The auto-generated schema is best-effort and only tries to infer basic
properties of the data. It is expected that users review and modify it as
needed._

### Training-Serving Skew Detection {#tfdv-training-serving-skew-detection}

#### Overview

The training-serving skew detector runs as a sub-component of TensorFlow Data
Validation and detects skew between training and serving data.

**Types of Skew**

Based on various production post-portems, we have reduced the various types of
skew to four key categories. Next we discuss each of these categories as well as
provide example scenarios under which they occur.

1.  **Schema Skew** occurs when the training and serving data do not conform to
    the same schema. As the schema describes the logical properties of the data,
    the training as well as serving data are expected to adhere to the same
    schema. Any expected deviations between the two (such as the label feature
    being only present in the training data but not in serving) should be
    specified through environments field in the schema.

    Since training data generation is a bulk data processing step, whereas
    (online) serving data generation is usually a latency sensitive step, it is
    common to have different code paths that generate training and serving data.
    This is a mistake.  Any discrepancy between these two codepaths (either due
    to developer error or inconsistent binary releases) can lead to schema skew.

    Example Scenario

    Bob wants to add a new feature to the model and adds it to the training
    data. The offline training metrics look great but online metrics are much
    worse. After hours of debugging Bob realises that he forgot to add the same
    feature in the serving code path. The model gave a high importance to this
    new feature and since it was unavailable at serving time, generated poor
    predictions leading to worse online metrics.

1.  **Feature Skew** occurs when the feature values that a model trains on are
    different from the feature values that it sees at serving time. This can
    happen due to multiple reasons, including:

    *   If an external data source that provides some feature values is modified
        between training and serving time.
    *   Inconsistent logic for generating features between training and serving.
        For example, if you apply some transformation only in one of the two
        code paths.

    Example Scenario

    Alice has a continuous machine learning pipeline where the serving data for
    today is logged and used to generate the next day's training data. In order
    to save space, she decides to only log the video id at serving time and
    fetch the video properties from a data store during training data
    generation.

    In doing so, she inadvertently introduces a skew that is specifically
    dangerous for newly uploaded and viral videos whose view time can change
    substantially between serving and training time (as shown below).

    <pre><code class="lang-proto">
     Serving Example           Training Example
     -------------------------  -------------------------
     features {                 features {
       feature {                  feature {
         key "vid"                  key "vid"
         value { int64_list {       value { int64_list {
           value 92392               value 92392
         }}                         }}
       }                          }
       feature {                  feature {
         key "views"               key "views"
         value { int_list {       value { bytes_list {
           value "<b>10</b>"                value "<b>10000</b>"  # skew
         }}                         }}
       }                          }
     }                          }
    </code></pre>

    This is an instance of feature skew since the training data sees an inflated
    number of views.

1.  **Distribution Skew** occurs when the distribution of feature values for
    training data is significantly different from serving data. One of the key
    causes for distribution skew is using either a completely different corpus
    for training data generation to overcome lack of initial data in the desired
    corpus. Another reason is a faulty sampling mechanism that only chooses a
    subsample of the serving data to train on.

    Example Scenario

    For instance, in order to compensate for an underrepresented slice of data,
    if a biased sampling is used without upweighting the downsampled examples
    appropriately, the distribution of feature values between training and
    serving data gets aritifically skewed.

1.  **Scoring/Serving Skew** is harder to detect and occurs when only a subset
    of the scored examples are actually served. Since labels are only available
    for the served examples and not the scored examples, only these examples are
    used for training. This implicitly causes the model to mispredict on the
    scored examples since they are gradually underrepresented in the training
    data.

    Example Scenario

    Consider an ad system which serves the top 10 ads. Of these 10 ads, only one
    of them may be clicked by the user. All 10 of these *served* examples are
    used for next days training -- 1 positive and 9 negative. However, at
    serving time the trained model was used to score 100s of ads. The other 90
    ads which were never served are implicitly removed from the training data.
    This results in an implicit feedback loop that mispredicts the lower ranked
    things further since they are not seen in the training data.

**Why should you care?**

Skew is hard to detect and is prevalent in many ML pipelines. There have been
several incidents where this has caused performance degradations and revenue
loss.

**What is supported currently?**

Currently, TensorFlow Data Validation supports schema skew, feature skew and
distribution skew detection.

### Drift Detection {#tfdv-drift-detection}

Drift detection is supported for categorical features and between consecutive
spans of data (i.e., between span N and span N+1), such as between different
days of training data. We express drift in terms of [L-infinity
distance](https://en.wikipedia.org/wiki/Chebyshev_distance), and you can set the
threshold distance so that you receive warnings when the drift is higher than is
acceptable. Setting the correct distance is typically an iterative process
requiring domain knowledge and experimentation.

## Using Visualizations to Check Your Data

TensorFlow Data Validation provides tools for visualizing the distribution of
feature values. By examining these distributions in a Jupyter notebook using
[Facets](https://pair-code.github.io/facets/)
you can catch common problems with data.

![Feature stats](images/feature_stats.png)

### Identifying Suspicious Distributions

You can identify common bugs in your data by using a Facets Overview
display to look for suspicious distributions of feature values.

#### Unbalanced Data

An unbalanced feature is a feature for which one value predominates. Unbalanced
features can occur naturally, but if a feature always has the same value you may
have a data bug. To detect unbalanced features in a Facets Overview, choose
"Non-uniformity" from the "Sort by" dropdown.

The most unbalanced features will be listed at the top of each feature-type
list. For example, the following screenshot shows one feature that is all zeros,
and a second that is highly unbalanced, at the top of the "Numeric Features"
list:

![Visualization of unbalanced data](images/unbalanced.png)

#### Uniformly Distributed Data

A uniformly distributed feature is one for which all possible values appear with
close to the same frequency. As with unbalanced data, this distribution can
occur naturally, but can also be produced by data bugs.

To detect uniformly distributed features in a Facets Overview, choose "Non-
uniformity" from the "Sort by" dropdown and check the "Reverse order" checkbox:

![Histogram of uniform data](images/uniform.png)

String data is represented using bar charts if there are 20 or fewer unique
values, and as a cumulative distribution graph if there are more than 20 unique
values. So for string data, uniform distributions can appear as either flat bar
graphs like the one above or straight lines like the one below:

![Line graph: cumulative distribution of uniform
data](images/uniform_cumulative.png)

##### Bugs That Can Produce Uniformly Distributed Data

Here are some common bugs that can produce uniformly distributed data:

*   Using strings to represent non-string data types such as dates. For example,
    you will have many unique values for a datetime feature with representations
    like "2017-03-01-11-45-03". Unique values will be distributed uniformly.

*   Including indices like "row number" as features. Here again you have many
    unique values.

#### Missing Data

To check whether a feature is missing values entirely:

1.  Choose "Amount missing/zero" from the "Sort by" drop-down.
2.  Check the "Reverse order" checkbox.
3.  Look at the "missing" column to see the percentage of instances with missing
    values for a feature.

A data bug can also cause incomplete feature values. For example you may expect
a feature's value list to always have three elements and discover that sometimes
it only has one. To check for incomplete values or other cases where feature
value lists don't have the expected number of elements:

1.  Choose "Value list length" from the "Chart to show" drop-down menu on the
    right.

2.  Look at the chart to the right of each feature row. The chart shows the
    range of value list lengths for the feature. For example, the highlighted
    row in the screenshot below shows a feature that has some zero-length value
    lists:

    ![Facets Overview display with feature with zero-length feature value
    lists](images/zero_length.png)

#### Large Differences in Scale Between Features

If your features vary widely in scale, then the model may have difficulties
learning. For example, if some features vary from 0 to 1 and others vary from 0
to 1,000,000,000, you have a big difference in scale. Compare the "max" and
"min" columns across features to find widely varying scales.

Consider normalizing feature values to reduce these wide variations.

#### Labels with Invalid Labels

TensorFlow's Estimators have restrictions on the type of data they accept as
labels. For example, binary classifiers typically only work with {0, 1} labels.

Review the label values in the Facets Overview and make sure they conform to the
[requirements of Estimators](https://github.com/tensorflow/docs/blob/master/site/en/r1/guide/feature_columns.md).
