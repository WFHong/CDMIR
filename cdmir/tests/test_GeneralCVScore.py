import numpy as np
from pandas import DataFrame
from cdmir.utils.local_score.cross_validated_base import GeneralCVScore

def test_score_function():
    data = np.array([[5.1, 3.5, 1.4, 0.2],
                     [4.9, 3, 1.4, 0.2],
                     [4.7, 3.2, 1.3, 0.2],
                     [4.6, 3.1, 1.5, 0.2],
                     [5.4, 3.9, 1.7, 0.4],
                     [4.9, 3.1, 1.5, 0.1],
                     [5.8, 4, 1.2, 0.2]])
    data_frame = DataFrame(data, columns=[f'Feature_{i}' for i in range(1, 5)])

    lambda_value = 0.01
    k_fold = 10
    general_cv_score = GeneralCVScore(data_frame, lambda_value, k_fold)

    # 选择要测试的变量和其父变量的索引
    variable_index = 2
    parent_indices = [0, 1]
    score = general_cv_score(variable_index, parent_indices)

    assert isinstance(score, float)
    assert score is not None, "GeneralCVScore calculation failed."