from causaldmir.utils.kernel.gaussian import GaussianKernel
import numpy as np

#arr1 = np.array([[1, 2, 3, 4], [1, 3, 4, 5]])
#arr2 = np.array([[1, 2, 3, 4], [3, 4, 5, 6]])

def test_gaussian_case1(): #shape(x)[1]==shape(y)[1]
    np.random.seed(10)
    xs=np.random.randn(20,20)
    ys=np.random.randn(30,20)

    gk=GaussianKernel()
    print(gk(xs,ys))

def test_gaussian_case2():#shape(x)[1]!=shape(y)[1]
    np.random.seed(10)
    xs = np.random.randn(20, 20)
    ys = np.random.randn(30, 30)

    gk = GaussianKernel()
    print(gk(xs, ys))

def test_gaussian_case3():#y is none
    np.random.seed(10)
    xs = np.random.randn(20, 20)
    #ys = np.array([])

    gk = GaussianKernel()
    print(gk(xs, ys=None))

#test_gaussian_case1()
#test_gaussian_case2()
#test_gaussian_case3()