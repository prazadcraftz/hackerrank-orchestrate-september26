import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from buy_or_wait.cache_audit import audit_source_cache
from buy_or_wait.evidence import Source,cache_key


class CacheAuditTests(unittest.TestCase):
    def test_reports_valid_fallback_without_mutating_invalid_primary(self):
        source=Source('message_x','message','user_x','','','','Confirmed.',{})
        fact={'type':'informational','scope':'informational','amount':'','currency':'',
              'effective_date':'','settlement_date':'','recurrence':'unknown',
              'source_identity':'message_x','quote':'Confirmed.','uncertainty':''}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            primary=root/f'{cache_key(source,"gemini-3.5-flash-lite")}.json'
            fallback=root/f'{cache_key(source,"gemini-3.6-flash")}.json'
            primary.write_text('{bad',encoding='utf-8')
            fallback.write_text(json.dumps({'facts':[fact],'unresolved':[]}),encoding='utf-8')
            result=audit_source_cache(source,root)
            self.assertTrue(result['ready'])
            self.assertEqual('gemini-3.6-flash',result['model'])
            self.assertEqual(['invalid','valid'],[item['state'] for item in result['attempts']])
            self.assertEqual('{bad',primary.read_text(encoding='utf-8'))

    def test_reports_missing_image_flash_cache(self):
        source=Source('image_x','image','user_x','','','','',{},'abc')
        with tempfile.TemporaryDirectory() as folder:
            result=audit_source_cache(source,Path(folder))
        self.assertFalse(result['ready'])
        self.assertEqual([{'model':'gemini-3.6-flash','state':'missing'}],result['attempts'])


if __name__=='__main__':
    unittest.main()
