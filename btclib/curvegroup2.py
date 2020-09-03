#!/usr/bin/env python3

# Copyright (C) 2020 The btclib developers
#
# This file is part of btclib. It is subject to the license terms in the
# LICENSE file found in the top-level directory of this distribution.
#
# No part of btclib including this file, may be copied, modified, propagated,
# or distributed except according to the terms contained in the LICENSE file.

"""Elliptic curve point multiplication functions.

The implemented algorithms are:
    - Montgomery Ladder
    - Scalar multiplication on basis 3
    - Fixed window
    - Sliding window
    - w-ary non-adjacent form (wNAF)

References:
    - https://en.wikipedia.org/wiki/Elliptic_curve_point_multiplication
    - https://cryptojedi.org/peter/data/eccss-20130911b.pdf
    - https://ecc2017.cs.ru.nl/slides/ecc2017school-castryck.pdf
    - https://cr.yp.to/bib/2003/joye-ladder.pdf

TODO:
    - Computational cost of the different multiplications
    - New alghoritms at the state-of-art:
        -https://hal.archives-ouvertes.fr/hal-00932199/document
        -https://iacr.org/workshops/ches/ches2006/presentations/Douglas%20Stebila.pdf
        -1-s2.0-S1071579704000395-main
        -https://crypto.stackexchange.com/questions/58506/what-is-the-curve-type-of-secp256k1
    - Constant time alghortims:
        -https://eprint.iacr.org/2011/338.pdf
    - Elegance in the code
    - Solve problem with wNAF and w=1
    - Multi_mult algorithm: why does it work?
"""


from typing import List

from .alias import INFJ, JacPoint
from .curvegroup import CurveGroup, convert_number_to_base


def mods(m: int, w: int) -> int:
    """Signed modulo function.

    FIXME:
    mods does NOT work for w=1.
    However the function in NOT really meant to be used for w=1
    For w=1 it always gives back -1 and enters an infinite loop
    """

    w2 = pow(2, w)
    M = m % w2
    return M - w2 if M >= (w2 / 2) else M


def _mult_sliding_window(m: int, Q: JacPoint, ec: CurveGroup, w: int = 4) -> JacPoint:
    """Scalar multiplication using "sliding window".

    It has the benefit that the pre-computation stage
    is roughly half as complex as the normal windowed method.
    It is not constant time.
    For 256-bit scalars choose w=4 or w=5.

    The input point is assumed to be on curve and
    the m coefficient is assumed to have been reduced mod n
    if appropriate (e.g. cyclic groups of order n).
    """

    if m < 0:
        raise ValueError(f"negative m: {hex(m)}")

    # a number cannot be written in basis 1 (ie w=0)
    if w <= 0:
        raise ValueError(f"non positive w: {w}")

    k = w - 1
    p = pow(2, k)

    # at each step one of the points in T will be added
    P = Q
    for _ in range(k):
        P = ec._double_jac(P)
    T = [P]
    for i in range(1, p):
        T.append(ec._add_jac(T[i - 1], Q))

    digits = convert_number_to_base(m, 2)

    R = INFJ
    i = 0
    while i < len(digits):
        if digits[i] == 0:
            R = ec._double_jac(R)
            i += 1
        else:
            j = len(digits) - i if (len(digits) - i) < w else w
            t = digits[i]
            for a in range(1, j):
                t = 2 * t + digits[i + a]

            if j < w:
                for b in range(i, (i + j)):
                    R = ec._double_jac(R)
                    if digits[b] == 1:
                        R = ec._add_jac(R, Q)
                return R
            else:
                for _ in range(w):
                    R = ec._double_jac(R)
                R = ec._add_jac(R, T[t - p])
                i += j
    return R


def _mult_w_NAF(m: int, Q: JacPoint, ec: CurveGroup, w: int = 4) -> JacPoint:
    """Scalar multiplication in Jacobian coordinates using wNAF.

    This implementation uses the same method called "w-ary non-adjacent form" (wNAF)
    we make use of the fact that point subtraction is as easy as point addition to perform fewer operations compared to sliding-window
    In fact, on Weierstrass curves, known P, -P can be computed on the fly.

    The input point is assumed to be on curve and
    the m coefficient is assumed to have been reduced mod n
    if appropriate (e.g. cyclic groups of order n).
    """
    if m < 0:
        raise ValueError(f"negative m: {hex(m)}")

    # a number cannot be written in basis 1 (ie w=0)
    if w <= 0:
        raise ValueError(f"non positive w: {w}")

    # This exception must be kept to satisfy the following while loop
    if m == 0:
        return INFJ

    i = 0

    M: List[int] = []
    while m > 0:
        if (m % 2) == 1:
            M.append(mods(m, w))
            m -= M[i]
        else:
            M.append(0)
        m //= 2
        i += 1

    p = i

    b = pow(2, w)

    Q2 = ec._double_jac(Q)
    T = [Q]
    for i in range(1, (b // 2)):
        T.append(ec._add_jac(T[i - 1], Q2))
    for i in range((b // 2), b):
        T.append(ec.negate_jac(T[i - (b // 2)]))

    R = INFJ
    for j in range(p - 1, -1, -1):
        R = ec._double_jac(R)
        if M[j] != 0:
            if M[j] > 0:
                # It adds the element jQ
                R = ec._add_jac(R, T[(M[j] - 1) // 2])
            else:
                # In this case it adds the opposite, ie -jQ
                R = ec._add_jac(R, T[(b // 2) - ((M[j] + 1) // 2)])
    return R