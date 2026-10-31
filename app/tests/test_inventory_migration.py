import json
from pathlib import Path
import tempfile
import unittest

from app.storage import Operations


class InventoryMigrationTests(unittest.TestCase):
    def test_extension_preserves_existing_operations_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'operations.sqlite3'
            ops=Operations(path,now=1793397600)
            with ops.db:
                # Reproduce an existing v1 inventory without touching physical telemetry.
                for table in ('demo_bins','samples','events'):
                    column='id' if table=='demo_bins' else 'bin_id'
                    ops.db.execute(f"DELETE FROM {table} WHERE {column} >= 'S25'")
                ops.put('inventory_version',1)
                first=ops.demo_bins()[0];first['fill_percent']=13;first['fault']='offline'
                ops.save_bin(first)
                ops.db.execute("INSERT INTO overrides VALUES ('S01','exclude')")
            before=json.dumps(first,sort_keys=True)
            samples=ops.history('S01');clock=ops.get('demo_now');ops.close()
            ops=Operations(path)
            self.assertEqual(len(ops.demo_bins()),36)
            self.assertEqual(json.dumps(ops.demo_bins()[0],sort_keys=True),before)
            self.assertEqual(ops.history('S01'),samples)
            self.assertEqual(ops.get('demo_now'),clock)
            self.assertEqual(ops.db.execute("SELECT mode FROM overrides WHERE bin_id='S01'").fetchone()[0],'exclude')
            self.assertEqual(len(ops.history('S36')),1345)
            count=ops.db.execute('SELECT COUNT(*) FROM samples').fetchone()[0];ops.close()
            ops=Operations(path)
            self.assertEqual(ops.db.execute('SELECT COUNT(*) FROM samples').fetchone()[0],count)
            self.assertEqual(ops.get('inventory_version'),2)
            ops.close()
