from types import SimpleNamespace as NS
import unittest
from kb_scanner.frontends.cpp.assert_profile import capture, _BODIES


def cursor(body, **kwargs):
    location = NS(file="/usr/include/assert.h", line=42, is_in_system_header=True)
    definition = NS(location=location, get_tokens=lambda: (NS(spelling=t) for t in ("assert ( expr ) "+body).split()))
    return NS(spelling="assert", kind=NS(name="MACRO_INSTANTIATION"), referenced=definition, **kwargs)


class AssertProfileTests(unittest.TestCase):
    def test_supported_profiles_and_parse_error(self):
        for body, expected in _BODIES.items():
            item = cursor(body)
            result = capture(item,"tu-a",False)["standardAssert"]
            self.assertEqual(expected,result["status"])
            self.assertEqual("tu-a",result["configuration"])
            self.assertEqual("observed-compilation-unit",result["scope"])
            self.assertEqual("unknown",capture(item,"tu-b",True)["standardAssert"]["status"])

    def test_unknown_local_missing_and_oversized_definitions(self):
        body=next(iter(_BODIES))
        for mutate in (lambda c:setattr(c,"spelling","custom"),
                       lambda c:setattr(c.kind,"name","CALL_EXPR"),
                       lambda c:setattr(c.referenced.location,"is_in_system_header",False),
                       lambda c:setattr(c.referenced.location,"file","custom.h"),
                       lambda c:setattr(c,"referenced",None)):
            item=cursor(body); mutate(item)
            self.assertEqual({},capture(item,"x",False))
        for body in ("custom", "x "*300):
            self.assertEqual({},capture(cursor(body),"x",False))
        item=cursor(body)
        item.referenced.get_tokens=lambda: (NS(spelling=t) for t in "assert ( bad ) 0".split())
        self.assertEqual({},capture(item,"x",False))
        item.referenced.get_tokens=lambda: (NS(spelling=t) for t in ("assert ( expr ) /*comment*/ "+next(iter(_BODIES))).split())
        self.assertEqual("disabled",capture(item,"x",False)["standardAssert"]["status"])
