.. _cache:

=====
Cache
=====

.. currentmodule:: django_mysql.cache

A MySQL-specific backend for Django's cache framework.


MySQLCache
==========

An efficient cache backend using a MySQL table, an alternative to Django's
database-agnostic ``DatabaseCache``. It has the following advantages:

* Each operation uses only one query, including the ``*_many`` methods. This is
  unlike ``DatabaseCache`` which uses multiple queries for nearly every
  operation.
* Automatic client-side ``zlib`` compression for objects larger than a given
  threshold. It is also easy to subclass and add your own serialization or
  compression schemes.
* Faster probabilistic culling behaviour during write operations, which you can
  also turn off and execute in a background task. This can be a bottleneck with
  Django's ``DatabaseCache`` since it culls on every write operation, executing
  a ``SELECT COUNT(*)`` which requires a full table scan.
* Integer counters with atomic ``incr()`` and ``decr()`` operations, like the
  ``MemcachedCache`` backend.

Usage
-----

To use, add an entry to your ``CACHES`` setting with:

* ``BACKEND`` set to ``django_mysql.cache.MySQLCache``

* ``LOCATION`` set to ``tablename``, the name of the table to use. This name
  can be whatever you want, as long as it's a valid table name that's not
  already being used in your database.

For example::

    CACHES = {
        'default': {
            'BACKEND': 'django_mysql.cache.MySQLCache',
            'LOCATION': 'my_super_cache'
        }
    }

You then need to make the table. The schema is *not* compatible with that of
``DatabaseCache``, so if you are switching, you will need to create a fresh
table.

Use the management command ``mysql_cache_migration`` to output a migration that
creates tables for all the ``MySQLCache`` instances you have configured. For
example::

    $ python manage.py mysql_cache_migration
    from django.db import migrations


    class Migration(migrations.Migration):

        operations = [
            migrations.RunSQL(
                """
                CREATE TABLE `my_super_cache` (
                    cache_key varchar(255) CHARACTER SET utf8 NOT NULL PRIMARY KEY,
                    value longblob NOT NULL,
                    value_type char(1) CHARACTER SET latin1 NOT NULL DEFAULT 'p',
                    expires BIGINT UNSIGNED NOT NULL
                );
                """,
                "DROP TABLE `my_super_cache`;"
            ),
        ]

Save this to a file in the ``migrations`` directory of one of your project's
apps. You might want to customize the SQL at this time, for example switching
the table to use the ``MEMORY`` storage engine.

Once the migration has run, the cache is ready to work!


Multiple Databases
------------------

If you use this with multiple databases, you'll also need to set up routing
instructions for the cache table. This can be done with the same method
that is described for ``DatabaseCache`` in the `Django manual
<https://docs.djangoproject.com/en/1.8/topics/cache/#database-caching>`_, apart
from the application name is ``django_mysql``.

.. note::

    Even if you aren't using multiple MySQL databases, it may be worth using
    routing anyway to put all your cache operations on a second connection -
    this way they won't be affected by transactions your main code runs.


Extra Details
-------------

``MySQLCache`` is fully compatible with Django's cache API, but it also extends
it and there are, of course, a few details to be aware of.


incr/decr
~~~~~~~~~

Like ``MemcachedCache`` (and unlike ``DatabaseCache``), ``incr`` and ``decr``
are atomic operations, and can only be used with ``int`` values. They have the
range of MySQL's ``SIGNED BIGINT`` (-9223372036854775808 to
9223372036854775807).


max_allowed_packet
~~~~~~~~~~~~~~~~~~

MySQL has a setting called ``max_allowed_packet``, which is the maximum size of
a query, including data. This therefore constrains the size of a cached value,
but you're more likely to run up against it first with the
``get_many``/``set_many`` operations.

`The MySQL 5.5 default <https://dev.mysql.com/doc/refman/5.5/en/server-system-
variables.html#sysvar_max_allowed_packet>`_ is 1 MB, and `the MySQL 5.6 default
<https://dev.mysql.com/doc/refman/5.6/en/server-system-
variables.html#sysvar_max_allowed_packet>`_ is 4MB, with which most
applications will be fine. You can tweak it as high as 1GB (if this isn't
enough, you should probably be considering another solution!).


culling
~~~~~~~

MySQL is designed to store data forever, and thus doesn't have a direct way of
setting expired rows to disappear. The expiration of old keys and the limiting
of rows to ``MAX_ENTRIES`` is therefore performed in the cache backend by
performing a cull operation when appropriate. This deletes expired keys first,
then if more than ``MAX_ENTRIES`` keys remain, it deletes 1 /
``CULL_FREQUENCY`` of them. The options and strategy are described in in more
detail in the `Django manual
<https://docs.djangoproject.com/en/1.8/topics/cache/#cache-arguments>`_.

Django's ``DatabaseCache`` performs a cull check on *every* write operation.
This runs a ``SELECT COUNT(*)`` on the table, which means a full-table scan.
Naturally, this takes a bit of time and becomes a bottleneck for medium or
large cache table sizes of caching. ``MySQLCache`` helps you solve this in two
ways:

1. The cull-on-write behaviour is probabilistic, by default running on 1% of
   writes. This is set with the ``CULL_PROBABILITY`` option, which should be a
   number between 0 and 1. For example, if you want to use the same
   cull-on-*every*-write behaviour as used by ``DatabaseCache`` (you probably
   don't), set ``CULL_PROBABILITY`` to 1.0::

       CACHES = {
           'default': {
               'BACKEND': 'django_mysql.cache.MySQLCache',
               'LOCATION': 'some_table_name',
               'OPTIONS': {
                   'CULL_PROBABILITY': 1.0
               }
           }
       }

2. The ``cull()`` method is available as a public method so you can set up your
   own culling schedule in background processing, never affecting any
   user-facing web requests. Set ``CULL_PROBABILITY`` to 0, and then set up
   your task. For example, if you are using **celery** you could use a task
   like this::

       @shared_task
       def clear_caches():
           caches['default'].cull()
           caches['other_cache'].cull()

   This functionality is also available as the management command
   ``cull_mysql_caches``, which you might run as a cron job. It performs
   ``cull()`` on all of your ``MySQLCache`` instances, or you can give it names
   to just cull those. For example, this::

       $ python manage.py cull_mysql_caches default other_cache

   ...will call ``caches['default'].cull()`` and
   ``caches['other_cache'].cull()``.


compression
~~~~~~~~~~~

Like the other Django cache backends, stored objects are serialized with
``pickle`` (except from integers, which are stored as integers so that the
``incr()`` and ``decr()`` operations will work). If pickled data has has a size
in bytes equal to or greater than the threshold defined by the option
``COMPRESS_MIN_LENGTH``, it will be compressed with ``zlib`` in Python before
being stored, reducing the on-disk size in MySQL and network costs for storage
and retrieval. The zlib level is set by the option ``COMPRESS_LEVEL``.

``COMPRESS_MIN_LENGTH`` defaults to 5000, and ``COMPRESS_LEVEL`` defaults to
the ``zlib`` default of 6. You can tune these options - for example, to
compress all objects >= 100 bytes at the maximum level of 9, pass the options
like so::

    CACHES = {
        'default': {
            'BACKEND': 'django_mysql.cache.MySQLCache',
            'LOCATION': 'some_table_name',
            'OPTIONS': {
                'COMPRESS_MIN_LENGTH': 100,
                'COMPRESS_LEVEL': 9
            }
        }
    }

To turn compression off, set ``COMPRESS_MIN_LENGTH`` to 0. The options only
affect new writes - any compressed values already in the table will remain
readable.


custom serialization
~~~~~~~~~~~~~~~~~~~~

You can implement your own serialization by subclassing ``MySQLCache``. It uses
two methods that you should override.

Values are stored in the table with two columns - ``value``, which is the blob
of binary data, and ``value_type``, a single latin1 character that specifies
the type of data in ``value``. MySQLCache by default uses three codes for
``value_type``:

* ``i`` - The blob is an integer. This is used so that counters can be
  deserialized by MySQL during the atomic ``incr()`` and ``decr()`` operations.
* ``p`` - The blob is a pickled Python object.
* ``z`` - The blob is a zlib-compressed pickled Python object.

For future compatibility, ``MySQLCache`` reserves all lower-case letters. For
custom types you can use upper-case letters.

The methods you need to override (and probably call ``super()`` from) are:

.. method:: encode(obj)

    Takes an object and returns a tuple ``(value, value_type)``, ready to be
    inserted as parameters into the SQL query.

.. method:: decode(value, value_type)

    Takes the pair of ``(value, value_type)`` as stored in the table and
    returns the deserialized object.

Studying the source of ``MySQLCache`` will probably give you the best way to
extend these methods for your use case.
