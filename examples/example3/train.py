from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np
import tensorflow as tf

from cluster import save_metrics_params, update_params_from_cmdline

default_params = {'model_dir': 'results/small/tt_home',  #
                  'batch_size': 50,  #
                  'total_iterations': 200000,  #
                  'iterations_per_eval': 10000,
                  'optimizer': 'Adam',  #
                  'lr_factor': 10000.0,  #
                  'layer_width': 50,  #
                  'layers': 8,  #
                  'input_dimension': 2,
                  'grid_size': 21}


class SignOptimizer(tf.train.GradientDescentOptimizer):
  def apply_gradients(self, grads_and_vars, *args, **kwargs):
    new_grad_var = [(tf.sign(grad), var) for grad, var in grads_and_vars]
    return super().apply_gradients(new_grad_var, *args, **kwargs)


def classify_array(array, grid_size):
  normed = (0.5 * (array + 1.0) * grid_size).astype(np.int32) % 2
  ans = (np.sum(normed, axis=1) % 2).astype(np.float32).reshape(-1, 1)
  return np.concatenate([1.0 - ans, ans], axis=1)


def generate_data(input_dimension, examples, grid_size, seed=None):
  np.random.seed(seed)
  lower, upper = (-1, 1)
  xs = np.random.uniform(lower, upper, (examples, input_dimension)).astype(np.float32)
  return xs, classify_array(xs, grid_size)


def input_from_fn(input_dimension, batch_size, total_examples, grid_size, seed=None):
  dataset_size = min(50000, total_examples)
  data = generate_data(input_dimension, dataset_size, grid_size=grid_size, seed=seed)
  ds = tf.data.Dataset.from_tensor_slices(data)
  ds = ds.repeat(total_examples // dataset_size).shuffle(dataset_size)
  ds = ds.batch(batch_size)
  xs, ys = ds.make_one_shot_iterator().get_next()
  return xs, ys


class Model(object):
  def __call__(self, inputs, params):
    y = inputs
    for i in range(params['layers'] - 1):
      y = tf.layers.dense(y, params['layer_width'], activation=tf.nn.tanh)
    y = tf.layers.dense(y, 2, activation=None)
    return y


optimizer_dict = {'RMSProp': (tf.train.RMSPropOptimizer, 0.0005),
                  'Adam': (tf.train.AdamOptimizer, 0.0003),
                  'SGD': (tf.train.GradientDescentOptimizer, 0.06),
                  'Sign': (SignOptimizer, 0.00005)}


def get_optimizer(opt_str, lr):
  opt, lr_base = optimizer_dict[opt_str]
  return opt(lr * lr_base)


def model_fn(features, labels, mode, params):
  """The model_fn argument for creating an Estimator."""
  global_step = tf.train.get_or_create_global_step()
  model = Model()

  input_data = features
  logits = model(input_data, params)
  predictions = {
    'classes': tf.argmax(logits, axis=1),
    'probabilities': tf.nn.softmax(logits, name='softmax_tensor')
  }
  if mode == tf.estimator.ModeKeys.PREDICT:
    return tf.estimator.EstimatorSpec(mode=mode, predictions=predictions)

  if mode == tf.estimator.ModeKeys.TRAIN:
    lr = params['lr_factor']
    optimizer = get_optimizer(params['optimizer'], lr)

    loss = tf.losses.softmax_cross_entropy(logits=logits, onehot_labels=labels)

    accuracy = tf.metrics.accuracy(tf.argmax(labels, axis=1), predictions['classes'])
    tf.identity(accuracy[1], name='train_accuracy')
    tf.summary.scalar('train_accuracy', accuracy[1])
    return tf.estimator.EstimatorSpec(
      mode=tf.estimator.ModeKeys.TRAIN,
      loss=loss,
      train_op=optimizer.minimize(loss, global_step))
  if mode == tf.estimator.ModeKeys.EVAL:
    loss = tf.losses.softmax_cross_entropy(logits=logits, onehot_labels=labels)
    accuracy = tf.metrics.accuracy(tf.argmax(labels, axis=1), predictions['classes'])
    metrics = {'accuracy': accuracy}

    return tf.estimator.EstimatorSpec(
      mode=tf.estimator.ModeKeys.EVAL,
      loss=loss,
      eval_metric_ops=metrics)


if __name__ == '__main__':
  tf.logging.set_verbosity(tf.logging.INFO)

  params = update_params_from_cmdline(default_params=default_params)

  # limit checkpointing (for grid searches)
  run_config = tf.estimator.RunConfig().replace(keep_checkpoint_max=1, log_step_count_steps=1000)

  classifier = tf.estimator.Estimator(
    model_fn=model_fn,
    model_dir=params.model_dir,
    config=run_config,
    params=params)

  accs = []
  for _ in range(min(1, params.total_iterations // params.iterations_per_eval)):
    classifier.train(
      input_fn=lambda: input_from_fn(params.input_dimension, params.batch_size,
                                     params.iterations_per_eval * params.batch_size,
                                     grid_size=params.grid_size))

    results = classifier.evaluate(input_fn=lambda: input_from_fn(params.input_dimension,
                                                                 params.batch_size, 10000,
                                                                 grid_size=params.grid_size))
    # Compute validation loss

    accs.append(results['accuracy'])

  last_acc = accs[-1]
  max_acc = max(accs)
  first_acc = accs[0]

  metrics = {'last_accuracy': last_acc,
             'max_accuracy': max_acc,
             'first_accuracy': first_acc}

  save_metrics_params(metrics=metrics, params=params)
