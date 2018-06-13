from cluster import save_metrics_params, update_params_from_cmdline
from sklearn.ensemble import RandomForestClassifier
from mnist import MNIST


# Default values of params
random_forest_args = {'n_estimators' : 10,
                      'criterion' : 'gini',
                      'max_features': 1.0,
                      'max_depth': None,
                      'n_jobs': -1,
                      'bootstrap': True,
                      'oob_score': False}


default_params = {'model_dir': '.',
                  'dataset': 'fashion_MNIST',
                  'random_forest_args': random_forest_args
                  }

params = update_params_from_cmdline(default_params=default_params)


paths = {'MNIST': 'mnist_data',
         'fashion_MNIST': 'fashion_data'}

data = MNIST(paths[params.dataset])

X_train, y_train = data.load_training()
X_test, y_test = data.load_testing()

clf = RandomForestClassifier(**params.random_forest_args)
clf.fit(X_train,y_train)

accuracy = clf.score(X_test,y_test)
print(accuracy)

metrics = {'RFC Score': accuracy}
save_metrics_params(metrics, params)
