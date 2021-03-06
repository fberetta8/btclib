#!/usr/bin/env python3

# Copyright (C) 2017-2020 The btclib developers
#
# This file is part of btclib. It is subject to the license terms in the
# LICENSE file found in the top-level directory of this distribution.
#
# No part of btclib including this file, may be copied, modified, propagated,
# or distributed except according to the terms contained in the LICENSE file.

"Tests for `btclib.electrum` module."

import json
from os import path

import pytest

from btclib import bip32, electrum, slip32


def test_mnemonic():
    lang = "en"

    entropy = 0x110AAAA03974D093EDA670121023CD0772
    eversion = "standard"
    # FIXME: is the following mnemonic obtained in Electrum
    # from the above entropy?
    mnemonic = "ability awful fetch liberty company spatial panda hat then canal ball crouch bunker"
    mnemonic2 = electrum.mnemonic_from_entropy(entropy, eversion, lang)
    assert mnemonic == mnemonic2

    entr = int(electrum.entropy_from_mnemonic(mnemonic, lang), 2)
    assert entr - entropy < 0xFFF

    passphrase = ""
    xprv = b"xprv9s21ZrQH143K2tn5j4pmrLXkS6dkbuX6mFhJfCxAwN6ofRo5ddCrLRWogKEs1AptPmLgrthKxU2csfBgkoKECWtj1XMRicRsoWawukaRQft"
    xprv2 = bip32.mxprv_from_electrum_mnemonic(mnemonic, passphrase)
    assert xprv2 == xprv

    eversion = "std"
    with pytest.raises(ValueError, match="unknown electrum mnemonic version: "):
        electrum.mnemonic_from_entropy(entropy, eversion, lang)

    unkn_ver = "ability awful fetch liberty company spatial panda hat then canal ball cross video"
    with pytest.raises(ValueError, match="unknown electrum mnemonic version: "):
        electrum.entropy_from_mnemonic(unkn_ver, lang)

    with pytest.raises(ValueError, match="unknown electrum mnemonic version: "):
        bip32.mxprv_from_electrum_mnemonic(unkn_ver, passphrase)

    for eversion in ("2fa", "2fa_segwit"):
        mnemonic = electrum.mnemonic_from_entropy(entropy, eversion, lang)
        with pytest.raises(ValueError, match="unmanaged electrum mnemonic version: "):
            bip32.mxprv_from_electrum_mnemonic(mnemonic, passphrase)

    mnemonic = "slender flight session office noodle hand couple option office wait uniform morning"
    assert "2fa_segwit" == electrum.version_from_mnemonic(mnemonic)[0]

    mnemonic = (
        "history recycle company awful donor fold beef nominee hard bleak bracket six"
    )
    assert "2fa" == electrum.version_from_mnemonic(mnemonic)[0]


def test_vectors():
    fname = "electrum_test_vectors.json"
    filename = path.join(path.dirname(__file__), "test_data", fname)
    with open(filename, "r") as f:
        test_vectors = json.load(f)

    lang = "en"
    for test_vector in test_vectors:
        mnemonic = test_vector[0]
        passphrase = test_vector[1]
        mxprv = test_vector[2]
        mxpub = test_vector[3]
        address = test_vector[4]  # "./0/0"

        if mnemonic != "":
            mxprv2 = bip32.mxprv_from_electrum_mnemonic(mnemonic, passphrase)
            assert mxprv2 == mxprv.encode()

            eversion, mnemonic = electrum.version_from_mnemonic(mnemonic)
            entr = int(electrum.entropy_from_mnemonic(mnemonic, lang), 2)
            mnem = electrum.mnemonic_from_entropy(entr, eversion, lang)
            assert mnem == mnemonic

        if mxprv != "":
            mxpub2 = bip32.xpub_from_xprv(mxprv)
            assert mxpub2 == mxpub.encode()

        xpub = bip32.derive(mxpub, "./0/0")
        address2 = slip32.address_from_xpub(xpub).decode("ascii")
        assert address2 == address
