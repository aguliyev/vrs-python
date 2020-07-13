"""provides an abstract class for all data access required for
vr.extras, and a concrete implementation based on seqrepo.

"""

from abc import ABC, abstractmethod
from collections import Sequence
from datetime import datetime
import functools
import itertools
import logging

from bioutils.accessions import coerce_namespace
import requests

from .utils import isoformat, base64url_to_hex


_logger = logging.getLogger(__name__)


class _DataProxy(ABC):
    """abstract class / interface for vr data needs
    
    The proxy MUST support the use of GA4GH sequence identifers (i.e.,
    `ga4gh:SQ...`) as keys, and return these identifiers among the
    aliases for a sequence.  These identifiers may be supported
    natively by the data source or synthesized by the proxy from the
    data source or synthesized.

    """

    @abstractmethod
    def get_sequence(identifier, start=None, end=None):
        """return the specified sequence or subsequence

        start and end are optional

        If the given sequence does not exist, KeyError is raised.

        >> dp.get_sequence("NM_000551.3", 0, 10)
        'CCTCGCCTCC'

        """

    @abstractmethod
    def get_metadata(identifier):
        """for a given identifier, return a structure (dict) containing
        sequence length, aliases, and other optional info

        If the given sequence does not exist, KeyError is raised.

        >> dp.get_metadata("NM_000551.3")
        {'added': '2016-08-24T05:03:11Z',
         'aliases': ['MD5:215137b1973c1a5afcf86be7d999574a',
                     'RefSeq:NM_000551.3',
                     'SEGUID:T12L0p2X5E8DbnL0+SwI4Wc1S6g',
                     'SHA1:4f5d8bd29d97e44f036e72f4f92c08e167354ba8',
                     'ga4gh:SQ.v_QTc1p-MUYdgrRv4LMT6ByXIOsdw3C_',
                     'gi:319655736'],
         'alphabet': 'ACGT',
         'length': 4560}

        """


    @functools.lru_cache()
    def translate_sequence_identifier(self, identifier, namespace=None):
        """Translate given identifier to a list of identifiers in the
        specified namespace.

        `identifier` must be a string
        `namespace` is case-sensitive

        On success, returns string identifier.  Raises KeyError if given
        identifier isn't found.

        """

        try:
            md = self.get_metadata(identifier)
        except (ValueError, KeyError, IndexError):
            raise KeyError(identifier)
        aliases = list(set(md["aliases"]))  # ensure uniqueness
        if namespace is not None:
            nsd = namespace + ":"
            aliases = [a for a in aliases if a.startswith(nsd)]
        return aliases


class _SeqRepoDataProxyBase(_DataProxy):
    # wraps seqreqpo classes in order to provide translation to/from
    # `ga4gh` identifiers.

    def get_metadata(self, identifier):
        md = self._get_metadata(identifier)
        md["aliases"] = list(a for a in md["aliases"])
        return md

    def get_sequence(self, identifier, start=None, end=None):
        return self._get_sequence(identifier, start=start, end=end)

    @abstractmethod
    def _get_metadata(self, identifier):  # pragma: no cover
        pass

    @abstractmethod
    def _get_sequence(self, identifier, start=None, end=None):  # pragma: no cover
        pass


class SeqRepoDataProxy(_SeqRepoDataProxyBase):
    """DataProxy based on a local instance of SeqRepo"""

    def __init__(self, sr):
        super().__init__()
        self.sr = sr

    def _get_sequence(self, identifier, start=None, end=None):
        # fetch raises KeyError if not found
        return self.sr.fetch(identifier, start, end)

    def _get_metadata(self, identifier):
        ns, a = coerce_namespace(identifier).split(":", 2)
        r = self.sr.aliases.find_aliases(namespace=ns, alias=a).fetchone()
        if r is None:
            raise KeyError(identifier) 
        seqinfo = self.sr.sequences.fetch_seqinfo(r["seq_id"])
        aliases = self.sr.aliases.fetch_aliases(r["seq_id"])
        return {
            "length": seqinfo["len"],
            "alphabet": seqinfo["alpha"],
            "added": isoformat(seqinfo["added"]),
            "aliases": [f"{a['namespace']}:{a['alias']}" for a in aliases],
            }
        return md


class SeqRepoRESTDataProxy(_SeqRepoDataProxyBase):
    """DataProxy based on a REST instance of SeqRepo, as provided by seqrepo-rest-services"""

    rest_version = "1"

    def __init__(self, base_url):
        super().__init__()
        self.base_url = f"{base_url}/{self.rest_version}/"

    def _get_sequence(self, identifier, start=None, end=None):
        url = self.base_url + f"sequence/{identifier}"
        _logger.info("Fetching " + url)
        params = {"start": start, "end": end}
        resp = requests.get(url, params=params)
        if resp.status_code == 404:
            raise KeyError(identifier) 
        resp.raise_for_status()
        return resp.text

    def _get_metadata(self, identifier):
        url = self.base_url + f"metadata/{identifier}"
        _logger.info("Fetching " + url)
        resp = requests.get(url)
        if resp.status_code == 404:
            raise KeyError(identifier) 
        resp.raise_for_status()
        data = resp.json()
        return data
    

class SequenceProxy(Sequence):
    """Provides efficient and transparent string-like access to a
    biological sequence

    """

    def __init__(self, dp, alias):
        self.dp = dp
        self.alias = alias
        self._md = self.dp.get_metadata(self.alias)
        
    def __str__(self):
        return self.dp.get_sequence(self.alias)

    def __len__(self):
        return self._md["length"]

    def __reversed__(self):
        raise NotImplementedError("Reversed iteration of a SequenceProxy is not implemented")

    def __getitem__(self, key):
        """return sequence for key (slice), fetching if necessary

        """

        if isinstance(key, int):
            key = slice(key, key+1)
        if key.step is not None:
            raise ValueError("Only contiguous sequence slices are supported")

        return self.dp.get_sequence(self.alias, key.start, key.stop)


 
# Future implementations
# * The RefGetDataProxy is waiting on support for sequence lookup by alias
# class RefGetDataProxy(_DataProxy):
#     def __init__(self, base_url):
#         super().__init__()
#         self.base_url = base_url



if __name__ == "__main__":
    seqrepo_rest_service_url = "http://localhost:5000/seqrepo" 
    dp = SeqRepoRESTDataProxy(base_url=seqrepo_rest_service_url) 
    sp = SequenceProxy(dp, "refseq:NM_000551.3")
