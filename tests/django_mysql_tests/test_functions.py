# -*- coding:utf-8 -*-
import hashlib
from unittest import skipIf

import django
from django.db.models import F
from django.test import TestCase

from django_mysql.models.functions import (
    CRC32, ELT, MD5, SHA1, SHA2, Abs, Ceiling, ConcatWS, Field, Floor,
    Greatest, LastInsertId, Least, Round, Sign
)
from django_mysql_tests.models import Alphabet

requiresDatabaseFunctions = skipIf(
    django.VERSION <= (1, 8),
    "Requires Database Functions from Django 1.8+"
)


@requiresDatabaseFunctions
class ComparisonFunctionTests(TestCase):

    def test_greatest(self):
        Alphabet.objects.create(d='A', e='B')
        ab = Alphabet.objects.annotate(best=Greatest('d', 'e')).first()
        self.assertEqual(ab.best, 'B')

    def test_greatest_takes_no_kwargs(self):
        with self.assertRaises(TypeError):
            Greatest('a', something='wrong')

    def test_least(self):
        Alphabet.objects.create(a=1, b=2, c=-1)
        ab = Alphabet.objects.annotate(worst=Least('a', 'b', 'c')).first()
        self.assertEqual(ab.worst, -1)


@requiresDatabaseFunctions
class NumericFunctionTests(TestCase):

    def test_abs(self):
        Alphabet.objects.create(a=-2)
        ab = Alphabet.objects.annotate(aaa=Abs('a')).first()
        self.assertEqual(ab.aaa, 2)

    def test_ceiling(self):
        Alphabet.objects.create(g=0.5)
        ab = Alphabet.objects.annotate(gceil=Ceiling('g')).first()
        self.assertEqual(ab.gceil, 1)

    def test_crc32(self):
        Alphabet.objects.create(d='AAAAAA')
        ab = Alphabet.objects.annotate(crc=CRC32('d')).first()
        # Precalculated this in MySQL prompt. Python's binascii.crc32 doesn't
        # match - maybe sign issues?
        self.assertEqual(ab.crc, 2854018686)

    def test_crc32_only_takes_one_arg_no_kwargs(self):
        with self.assertRaises(TypeError):
            CRC32('d', 'c')

        with self.assertRaises(TypeError):
            CRC32('d', something='wrong')

    def test_floor(self):
        Alphabet.objects.create(g=1.5)
        ab = Alphabet.objects.annotate(gfloor=Floor('g')).first()
        self.assertEqual(ab.gfloor, 1)

    def test_round(self):
        Alphabet.objects.create(g=24.459)
        ab = Alphabet.objects.annotate(ground=Round('g')).get()
        self.assertEqual(ab.ground, 24)

    def test_round_up(self):
        Alphabet.objects.create(g=27.859)
        ab = Alphabet.objects.annotate(ground=Round('g')).get()
        self.assertEqual(ab.ground, 28)

    def test_round_places(self):
        Alphabet.objects.create(a=81731)
        ab = Alphabet.objects.annotate(around=Round('a', -2)).get()
        self.assertEqual(ab.around, 81700)

    def test_sign(self):
        Alphabet.objects.create(a=123, b=0, c=-999)
        ab = Alphabet.objects.annotate(
            asign=Sign('a'),
            bsign=Sign('b'),
            csign=Sign('c'),
        ).first()
        self.assertEqual(ab.asign, 1)
        self.assertEqual(ab.bsign, 0)
        self.assertEqual(ab.csign, -1)


@requiresDatabaseFunctions
class StringFunctionTests(TestCase):

    def test_concat_ws(self):
        Alphabet.objects.create(d='AAA', e='BBB')
        ab = Alphabet.objects.annotate(de=ConcatWS('d', 'e')).first()
        self.assertEqual(ab.de, 'AAA,BBB')

    def test_concat_ws_integers(self):
        Alphabet.objects.create(a=1, b=2)
        ab = Alphabet.objects.annotate(ab=ConcatWS('a', 'b')).first()
        self.assertEqual(ab.ab, '1,2')

    def test_concat_ws_skips_nulls(self):
        Alphabet.objects.create(d='AAA', e=None, f=2)
        ab = Alphabet.objects.annotate(de=ConcatWS('d', 'e', 'f')).first()
        self.assertEqual(ab.de, 'AAA,2')

    def test_concat_ws_separator(self):
        Alphabet.objects.create(d='AAA', e='BBB')
        ab = (
            Alphabet.objects.annotate(de=ConcatWS('d', 'e', separator=':'))
                            .first()
        )
        self.assertEqual(ab.de, 'AAA:BBB')

    def test_concat_ws_separator_null_returns_none(self):
        Alphabet.objects.create(a=1, b=2)
        concat = ConcatWS('a', 'b', separator=None)
        ab = Alphabet.objects.annotate(ab=concat).first()
        self.assertEqual(ab.ab, None)

    def test_concat_ws_separator_field(self):
        Alphabet.objects.create(a=1, d='AAA', e='BBB')
        concat = ConcatWS('d', 'e', separator=F('a'))
        ab = Alphabet.objects.annotate(de=concat).first()
        self.assertEqual(ab.de, 'AAA1BBB')

    def test_concat_ws_bad_arg(self):
        with self.assertRaises(ValueError) as cm:
            ConcatWS('a', 'b', separataaa=',')
        self.assertIn('Invalid keyword arguments for ConcatWS: separataaa',
                      str(cm.exception))

    def test_concat_ws_too_few_fields(self):
        with self.assertRaises(ValueError) as cm:
            ConcatWS('a')
        self.assertIn('ConcatWS must take at least two expressions',
                      str(cm.exception))

    def test_concat_ws_then_lookups_from_textfield(self):
        Alphabet.objects.create(d='AAA', e='BBB')
        Alphabet.objects.create(d='AAA', e='CCC')
        ab = (
            Alphabet.objects.annotate(de=ConcatWS('d', 'e', separator=':'))
                            .filter(de__endswith=':BBB')
                            .first()
        )
        self.assertEqual(ab.de, 'AAA:BBB')

    def test_elt_simple(self):
        Alphabet.objects.create(a=2)
        ab = Alphabet.objects.annotate(elt=ELT('a', ['apple', 'orange'])).get()
        self.assertEqual(ab.elt, 'orange')
        ab = Alphabet.objects.annotate(elt=ELT('a', ['apple'])).get()
        self.assertEqual(ab.elt, None)

    def test_field_simple(self):
        Alphabet.objects.create(d='a')
        ab = Alphabet.objects.annotate(dp=Field('d', ['a', 'b'])).first()
        self.assertEqual(ab.dp, 1)
        ab = Alphabet.objects.annotate(dp=Field('d', ['b', 'a'])).first()
        self.assertEqual(ab.dp, 2)
        ab = Alphabet.objects.annotate(dp=Field('d', ['c', 'd'])).first()
        self.assertEqual(ab.dp, 0)

    def test_order_by(self):
        Alphabet.objects.create(a=1, d='AAA')
        Alphabet.objects.create(a=2, d='CCC')
        Alphabet.objects.create(a=4, d='BBB')
        Alphabet.objects.create(a=3, d='BBB')
        avalues = list(
            Alphabet.objects.order_by(Field('d', ['AAA', 'BBB']), 'a')
                            .values_list('a', flat=True)
        )
        self.assertEqual(avalues, [2, 1, 3, 4])


@requiresDatabaseFunctions
class EncryptionFunctionTests(TestCase):

    def test_md5_string(self):
        string = 'A string'
        Alphabet.objects.create(d=string)
        pymd5 = hashlib.md5(string.encode('ascii')).hexdigest()
        ab = Alphabet.objects.annotate(md5=MD5('d')).first()
        self.assertEqual(ab.md5, pymd5)

    def test_sha1_string(self):
        string = 'A string'
        Alphabet.objects.create(d=string)
        pysha1 = hashlib.sha1(string.encode('ascii')).hexdigest()
        ab = Alphabet.objects.annotate(sha=SHA1('d')).first()
        self.assertEqual(ab.sha, pysha1)

    def test_sha2_string(self):
        string = 'A string'
        Alphabet.objects.create(d=string)

        for hash_len in (224, 256, 384, 512):
            sha_func = getattr(hashlib, 'sha{}'.format(hash_len))
            pysha = sha_func(string.encode('ascii')).hexdigest()
            ab = Alphabet.objects.annotate(sha=SHA2('d', hash_len)).first()
            self.assertEqual(ab.sha, pysha)

    def test_sha2_string_hash_len_default(self):
        string = 'A string'
        Alphabet.objects.create(d=string)
        pysha512 = hashlib.sha512(string.encode('ascii')).hexdigest()
        ab = Alphabet.objects.annotate(sha=SHA2('d')).first()
        self.assertEqual(ab.sha, pysha512)

    def test_sha2_bad_hash_len(self):
        with self.assertRaises(ValueError):
            SHA2('a', 123)


@requiresDatabaseFunctions
class InformationFunctionTests(TestCase):

    def test_last_insert_id(self):
        Alphabet.objects.create(a=7891)
        Alphabet.objects.update(a=LastInsertId('a') + 1)
        lid = LastInsertId.get()
        self.assertEqual(lid, 7891)

    def test_last_insert_id_other_db_connection(self):
        Alphabet.objects.using('other').create(a=9191)
        Alphabet.objects.using('other').update(a=LastInsertId('a') + 9)
        lid = LastInsertId.get(using='other')
        self.assertEqual(lid, 9191)

    def test_last_insert_id_in_query(self):
        ab1 = Alphabet.objects.create(a=3719, b=717612)
        ab2 = Alphabet.objects.create(a=1838, b=12636)

        # Delete but store value of b and re-assign it to first second Alphabet
        Alphabet.objects.filter(id=ab1.id, b=LastInsertId('b')).delete()
        Alphabet.objects.filter(id=ab2.id).update(b=LastInsertId())

        ab = Alphabet.objects.get()
        self.assertEqual(ab.b, 717612)


@skipIf(django.VERSION >= (1, 8),
        "Requires old Django version without Database Functions")
class OldDjangoFunctionTests(TestCase):

    def test_single_arg_doesnt_work(self):
        with self.assertRaises(ValueError):
            CRC32('name')

    def test_multi_arg_doesnt_work(self):
        with self.assertRaises(ValueError):
            Greatest('a', 'b')

    def test_concat_ws_doesnt_work(self):
        with self.assertRaises(ValueError):
            ConcatWS('a', 'b', separator='::')
