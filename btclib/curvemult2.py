#!/usr/bin/env python3

# Copyright (C) 2017-2020 The btclib developers
#
# This file is part of btclib. It is subject to the license terms in the
# LICENSE file found in the top-level directory of this distribution.
#
# No part of btclib including this file, may be copied, modified, propagated,
# or distributed except according to the terms contained in the LICENSE file.

"""Several Elliptic curve point multiplication functions."""

import heapq
from typing import List, Sequence, Tuple

from .alias import INFJ, Integer, JacPoint, Point
from .curve import Curve, CurveGroup, _jac_from_aff, _mult_jac
from .curves import secp256k1
from .utils import int_from_integer


def _mult_jac_mont_ladder(m: int, Q: JacPoint, ec: CurveGroup) -> JacPoint:
    """Scalar multiplication of a curve point in Jacobian coordinates.
    This implementation uses 'montgomery ladder' algorithm,
    jacobian coordinates.
    It is constant-time if the binary size of Q remains the same.
    The input point is assumed to be on curve,
    m is assumed to have been reduced mod n if appropriate
    (e.g. cyclic groups of order n).
    """

    if m < 0:
        raise ValueError(f"negative m: {hex(m)}")

    if Q == INFJ:
        return Q

    R = INFJ  # initialize as infinity point
    for m in [int(i) for i in bin(m)[2:]]:  # goes through binary digits
        if m == 0:
            Q = ec._add_jac(R, Q)
            R = ec._add_jac(R, R)
        else:
            R = ec._add_jac(R, Q)
            Q = ec._add_jac(Q, Q)
    return R


def mult_mont_ladder(m: Integer, Q: Point = None, ec: Curve = secp256k1) -> Point:
    """
    Point multiplication, implemented using 'montgomery ladder' algorithm to run in constant time. 
    This can be beneficial when timing  measurements are exposed to an attacker performing a side-channel attack. 
    This algorithm has the same speed as the double-and-add approach except that it computes the same number 
    of point additions and doubles regardless of the value of the multiplicand m.

    Computations use Jacobian coordinates and binary decomposition of m.
    """
    if Q is None:
        QJ = ec.GJ
    else:
        ec.require_on_curve(Q)
        QJ = _jac_from_aff(Q)

    m = int_from_integer(m) % ec.n
    R = _mult_jac_mont_ladder(m, QJ, ec)
    return ec._aff_from_jac(R)


def numberToBase(n, b):
    "Returns a list of the digits of n written in basis b"

    if n == 0:
        return [0]
    digits = []
    while n:
        digits.append(int(n % b))
        n //= b
    return digits[::-1]


def _mult_jac_base_3(m: int, Q: JacPoint, ec: CurveGroup) -> JacPoint:
    """Scalar multiplication of a curve point in Jacobian coordinates.
    This implementation uses the same idea of "double and add" algorithm,
    but with the scalar radix 3.
    It is not constant time.
    The input point is assumed to be on curve,
    m is assumed to have been reduced mod n if appropriate
    (e.g. cyclic groups of order n).
    """

    if m < 0:
        raise ValueError(f"negative m: {hex(m)}")

    if Q == INFJ:
        return Q

    """
    Fare array T con Q0, Q1, Q2
    Pongo
    R = T[ultima cifra a sinstra nella rapp mod 3 di m]
    for i = [penultima cifra a sintra...] down to 0
    R = 3R
    R = R + T[i]
    End for

    """

    T: List[JacPoint] = []
    T.append(INFJ)
    for i in range(1, 3):
        T.append(ec._add_jac(T[i - 1], Q))

    M = numberToBase(m, 3)

    R = T[M[0]]

    for i in range(1, len(M)):
        R2 = ec._add_jac(R, R)
        R = ec._add_jac(R2, R)
        R = ec._add_jac(R, T[M[i]])

    return R


def mult_base_3(m: Integer, Q: Point = None, ec: Curve = secp256k1) -> Point:
    """Point multiplication, implemented using 'double and add' but changing the scalar radix to 3.

    Computations use Jacobian coordinates and decomposition of m basis 3.
    """
    if Q is None:
        QJ = ec.GJ
    else:
        ec.require_on_curve(Q)
        QJ = _jac_from_aff(Q)

    m = int_from_integer(m) % ec.n
    R = _mult_jac_base_3(m, QJ, ec)
    return ec._aff_from_jac(R)


def _mult_jac_fixed_window(m: int, w: int, Q: JacPoint, ec: CurveGroup) -> JacPoint:
    """Scalar multiplication of a curve point in Jacobian coordinates.
    This implementation uses the method called "fixed window"
    It is not constant time.
    For about 256-bit scalars choose w=4 or w=5
    The input point is assumed to be on curve,
    m is assumed to have been reduced mod n if appropriate
    (e.g. cyclic groups of order n).
    """
    if m < 0:
        raise ValueError(f"negative m: {hex(m)}")

    if Q == INFJ:
        return Q

    # Forse bisognerebbe modificarlo per renderlo ok anche per w=0
    if w <= 0:
        raise ValueError(f"w must be strictly positive")

    b = pow(2, w)

    T: List[JacPoint] = []
    T.append(INFJ)
    for i in range(1, b):
        T.append(ec._add_jac(T[i - 1], Q))

    M = numberToBase(m, b)

    R = T[M[0]]

    for i in range(1, len(M)):
        for j in range(w):
            R = ec._add_jac(R, R)
        R = ec._add_jac(R, T[M[i]])

    return R


def mult_fixed_window(m: Integer, w: Integer, Q: Point = None, ec: Curve = secp256k1) -> Point:
    """Point multiplication, implemented using 'fixed window' method.

    Computations use Jacobian coordinates and decomposition of m on basis 2^w.
    """

    if Q is None:
        QJ = ec.GJ
    else:
        ec.require_on_curve(Q)
        QJ = _jac_from_aff(Q)

    m = int_from_integer(m) % ec.n
    w = int_from_integer(w)
    R = _mult_jac_fixed_window(m, w, QJ, ec)
    return ec._aff_from_jac(R)


# Sliding window ??


def mods(m: int, w: int) -> int:
    w2 = pow(2, w)  # cannot name it 2w
    M = m % w2
    if M >= (w2 / 2):
        return M - w2
    else:
        return M


def _mult_jac_w_NAF(m: int, w: int, Q: JacPoint, ec: CurveGroup) -> JacPoint:
    """Scalar multiplication of a curve point in Jacobian coordinates.
    This implementation uses the same method called "w-ary non-adjacent form" (wNAF)
    Not always resistent against cache-timing attacks
    The input point is assumed to be on curve,
    m is assumed to have been reduced mod n if appropriate
    (e.g. cyclic groups of order n).
    """
    if m < 0:
        raise ValueError(f"negative m: {hex(m)}")

    if Q == INFJ:
        return Q

    i = 0

    p = []

    while (m > 0):
        if (m % 2) == 1:
            p[i] = mods(m, w)
            d = d - p[i]
        else:
            p[i] = 0
        d = d / 2
        i = i + 1

    b = pow(2, w)

    # The values of even points must be cancelled
    T = []
    T[0] = INFJ
    for i in range(1, b - 1):
        T[i] = ec._add_jac(T[i - 1], Q)
    for i in range(1 - b, -1):
        T[i] = ec.negate(T[-i])

    R = INFJ

    for j in range(i - 1, 0):
        R = ec._add_jac(R, R)
        if p[j] != 0:
            R = ec._add_jac(R, T[p[j]])

    return R