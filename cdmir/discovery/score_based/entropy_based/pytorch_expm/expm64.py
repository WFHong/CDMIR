"""
Adaptation of expm and expm_frechet in numpy for torch
"""

#
# Authors: Travis Oliphant, March 2002
#          Anthony Scopatz, August 2012 (Sparse Updates)
#          Jake Vanderplas, August 2012 (Sparse Updates)
#

from __future__ import absolute_import, division, print_function

import math

import numpy as np
import scipy.special

import torch

def _onenorm_matrix_power_nnm(A, p):
    """
    Compute the 1-norm of a non-negative integer power of a non-negative matrix.

    Parameters
    ----------
    A : a square ndarray or matrix or sparse matrix
        Input matrix with non-negative entries.
    p : non-negative integer
        The power to which the matrix is to be raised.

    Returns
    -------
    out : float
        The 1-norm of the matrix power p of A.

    """
    # check input
    if int(p) != p or p < 0:
        raise ValueError('expected non-negative integer p')
    p = int(p)
    if len(A.shape) != 2 or A.shape[0] != A.shape[1]:
        raise ValueError('expected A to be like a square matrix')

    # Explicitly make a column vector so that this works when A is a
    # numpy matrix (in addition to ndarray and sparse matrix).
    v = torch.ones((A.shape[0], 1), dtype=A.dtype, device=A.device)
    M = A.t()
    for _ in range(p):
        v = M.mm(v)
    return torch.max(v).item()


def _onenorm(A):
    return torch.norm(A, 1).item()


def _ident_like(A):
    return torch.eye(A.shape[0], A.shape[1], dtype=A.dtype, device=A.device)

class _ExpmPadeHelper(object):
    """
    Help lazily evaluate a matrix exponential.

    The idea is to not do more work than we need for high expm precision,
    so we lazily compute matrix powers and store or precompute
    other properties of the matrix.

    """
    def __init__(self, A):
        """
        Initialize the object.

        Parameters
        ----------
        A : a dense or sparse square numpy matrix or ndarray
            The matrix to be exponentiated.
        """
        self.A = A
        self._A2 = None
        self._A4 = None
        self._A6 = None
        self._A8 = None
        self._A10 = None
        self._d4_exact = None
        self._d6_exact = None
        self._d8_exact = None
        self._d10_exact = None
        self._d4_approx = None
        self._d6_approx = None
        self._d8_approx = None
        self._d10_approx = None
        self.ident = _ident_like(A)

    @property
    def A2(self):
        if self._A2 is None:
            self._A2 = self.A.mm(self.A)
        return self._A2

    @property
    def A4(self):
        if self._A4 is None:
            self._A4 = self.A2.mm(self.A2)
        return self._A4

    @property
    def A6(self):
        if self._A6 is None:
            self._A6 = self.A4.mm(self.A2)
        return self._A6

    @property
    def A8(self):
        if self._A8 is None:
            self._A8 = self.A6.mm(self.A2)
        return self._A8

    @property
    def A10(self):
        if self._A10 is None:
            self._A10 = self.A4.mm(self.A6)
        return self._A10

    @property
    def d4_tight(self):
        if self._d4_exact is None:
            self._d4_exact = _onenorm(self.A4)**(1/4.)
        return self._d4_exact

    @property
    def d6_tight(self):
        if self._d6_exact is None:
            self._d6_exact = _onenorm(self.A6)**(1/6.)
        return self._d6_exact

    @property
    def d8_tight(self):
        if self._d8_exact is None:
            self._d8_exact = _onenorm(self.A8)**(1/8.)
        return self._d8_exact

    @property
    def d10_tight(self):
        if self._d10_exact is None:
            self._d10_exact = _onenorm(self.A10)**(1/10.)
        return self._d10_exact

    @property
    def d4_loose(self):
        return self.d4_tight

    @property
    def d6_loose(self):
        return self.d6_tight

    @property
    def d8_loose(self):
        return self.d8_tight

    @property
    def d10_loose(self):
        return self.d10_tight

    def pade3(self):
        b = (120., 60., 12., 1.)
        U = self.A.mm(b[3]*self.A2 + b[1]*self.ident)
        V = b[2]*self.A2 + b[0]*self.ident
        return U, V

    def pade5(self):
        b = (30240., 15120., 3360., 420., 30., 1.)
        U = self.A.mm(b[5]*self.A4 + b[3]*self.A2 + b[1]*self.ident)
        V = b[4]*self.A4 + b[2]*self.A2 + b[0]*self.ident
        return U, V


    def pade7(self):
        b = (17297280., 8648640., 1995840., 277200., 25200., 1512., 56., 1.)
        U = self.A.mm(b[7]*self.A6 + b[5]*self.A4 + b[3]*self.A2 + b[1]*self.ident)
        V = b[6]*self.A6 + b[4]*self.A4 + b[2]*self.A2 + b[0]*self.ident
        return U, V

    def pade9(self):
        b = (17643225600., 8821612800., 2075673600., 302702400., 30270240.,
                2162160., 110880., 3960., 90., 1.)
        U = self.A.mm(b[9]*self.A8 + b[7]*self.A6 + b[5]*self.A4
                    + b[3]*self.A2 + b[1]*self.ident)
        V = (b[8]*self.A8 + b[6]*self.A6 + b[4]*self.A4 +
                b[2]*self.A2 + b[0]*self.ident)
        return U, V

    def pade13_scaled(self, s):
        b = (64764752532480000., 32382376266240000., 7771770303897600.,
                1187353796428800., 129060195264000., 10559470521600.,
                670442572800., 33522128640., 1323241920., 40840800., 960960.,
                16380., 182., 1.)
        B = self.A * 2**-s
        B2 = self.A2 * 2**(-2*s)
        B4 = self.A4 * 2**(-4*s)
        B6 = self.A6 * 2**(-6*s)
        U2 = B6.mm(b[13]*B6 + b[11]*B4 + b[9]*B2)
        U = B.mm(U2 + b[7]*B6 + b[5]*B4 + b[3]*B2 + b[1]*self.ident)
        V2 = B6.mm(b[12]*B6 + b[10]*B4 + b[8]*B2)
        V = V2 + b[6]*B6 + b[4]*B4 + b[2]*B2 + b[0]*self.ident
        return U, V


def expm64(A):
    """
    Compute the matrix exponential using Pade approximation.

    Parameters
    ----------
    A : (M,M) array_like or sparse matrix
        2D Array or Matrix (sparse or dense) to be exponentiated

    Returns
    -------
    expA : (M,M) ndarray
        Matrix exponential of `A`

    Notes
    -----
    This is algorithm (6.1) which is a simplification of algorithm (5.1).

    .. versionadded:: 0.12.0

    References
    ----------
    .. [1] Awad H. Al-Mohy and Nicholas J. Higham (2009)
           "A New Scaling and Squaring Algorithm for the Matrix Exponential."
           SIAM Journal on Matrix Analysis and Applications.
           31 (3). pp. 970-989. ISSN 1095-7162

    """
    return _expm(A)


def _expm(A):
    # Core of expm, separated to allow testing exact and approximate
    # algorithms.

    # Avoid indiscriminate asarray() to allow sparse or other strange arrays.
    if len(A.shape) != 2 or A.shape[0] != A.shape[1]:
        raise ValueError('expected a square matrix')

    # Trivial case
    if A.shape == (1, 1):
        return torch.exp(A)

    # Track functions of A to help compute the matrix exponential.
    h = _ExpmPadeHelper(A)


    # Try Pade order 3.
    eta_1 = max(h.d4_loose, h.d6_loose)
    if eta_1 < 1.495585217958292e-002 and _ell(h.A, 3) == 0:
        U, V = h.pade3()
        return _solve_P_Q(U, V)

    # Try Pade order 5.
    eta_2 = max(h.d4_tight, h.d6_loose)
    if eta_2 < 2.539398330063230e-001 and _ell(h.A, 5) == 0:
        U, V = h.pade5()
        return _solve_P_Q(U, V)

    # Try Pade orders 7 and 9.
    eta_3 = max(h.d6_tight, h.d8_loose)
    if eta_3 < 9.504178996162932e-001 and _ell(h.A, 7) == 0:
        U, V = h.pade7()
        return _solve_P_Q(U, V)
    if eta_3 < 2.097847961257068e+000 and _ell(h.A, 9) == 0:
        U, V = h.pade9()
        return _solve_P_Q(U, V)

    # Use Pade order 13.
    eta_4 = max(h.d8_loose, h.d10_loose)
    eta_5 = min(eta_3, eta_4)
    theta_13 = 4.25

    s = max(int(np.ceil(np.log2(eta_5 / theta_13))), 0)

    s += _ell(2**-s * h.A, 13)
    U, V = h.pade13_scaled(s)
    X = _solve_P_Q(U, V)
    return torch.matrix_power(X, 2**s)


def _solve_P_Q(U, V):
    P = U + V
    Q = -U + V
    return torch.solve(P, Q)[0]


def _ell(A, m):
    """
    A helper function for expm_2009.

    Parameters
    ----------
    A : linear operator
        A linear operator whose norm of power we care about.
    m : int
        The power of the linear operator

    Returns
    -------
    value : int
        A value related to a bound.

    """
    if len(A.shape) != 2 or A.shape[0] != A.shape[1]:
        raise ValueError('expected A to be like a square matrix')

    p = 2*m + 1

    # The c_i are explained in (2.2) and (2.6) of the 2005 expm paper.
    # They are coefficients of terms of a generating function series expansion.
    choose_2p_p = scipy.special.comb(2*p, p, exact=True)
    abs_c_recip = float(choose_2p_p * math.factorial(2*p + 1))

    # This is explained after Eq. (1.2) of the 2009 expm paper.
    # It is the "unit roundoff" of IEEE double precision arithmetic.
    u = 2.**-53

    # Compute the one-norm of matrix power p of abs(A).
    A_abs_onenorm = _onenorm_matrix_power_nnm(abs(A), p)

    # Treat zero norm as a special case.
    if not A_abs_onenorm:
        return 0

    alpha = A_abs_onenorm / (_onenorm(A) * abs_c_recip)
    return max(int(np.ceil(np.log2(alpha/u) / (2 * m))), 0)
