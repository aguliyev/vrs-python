# flake8: noqa
"""Public interface to the GA4GH Variation Representation reference
implementation

Import as:

>>> from ga4gh.vr import models, computed_id, serialize

Deprecation and change notices are provided only for definitions
obtained by importing ga4gh.vr as shown above.

"""


__all__ = """ga4gh_digest identify models schema_path serialize""".split()


import warnings
from pkg_resources import get_distribution, DistributionNotFound

try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:
    __version__ = "unknown"
finally:
    del get_distribution, DistributionNotFound

from ._internal import ga4gh_digest, identify, models, schema_path, serialize
