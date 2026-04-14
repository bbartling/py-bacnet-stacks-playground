# Auto-loaded by Python at startup (https://docs.python.org/3/library/site.html).
# gevent entry points call pkg_resources.require("zope.interface"); wheels register as
# "zope-interface", so vctl fails with DistributionNotFound unless we alias or patch resolve().
import pkg_resources

_ws = pkg_resources.working_set
_hyp, _dot = "zope-interface", "zope.interface"
if _hyp in _ws.by_key:
    _ws.by_key.setdefault(_dot, _ws.by_key[_hyp])

_orig_resolve = pkg_resources.WorkingSet.resolve


def _resolve_patched(self, requirements, *args, **kwargs):
    try:
        return _orig_resolve(self, requirements, *args, **kwargs)
    except pkg_resources.DistributionNotFound:
        if _hyp in self.by_key:
            self.by_key.setdefault(_dot, self.by_key[_hyp])
        return _orig_resolve(self, requirements, *args, **kwargs)


pkg_resources.WorkingSet.resolve = _resolve_patched
