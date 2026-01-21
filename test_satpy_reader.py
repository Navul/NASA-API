import sys
from satpy import available_readers

print("Checking satpy readers...")
readers = available_readers()

print(f"\nTotal readers available: {len(readers)}")
print(f"\nahi_hsd reader available: {'ahi_hsd' in readers}")

print("\nAHI/Himawari related readers:")
ahi_readers = [r for r in readers if 'ahi' in r.lower() or 'himawari' in r.lower()]
if ahi_readers:
    for r in ahi_readers:
        print(f"  ✓ {r}")
else:
    print("  ✗ None found")

print("\nAll available readers:")
for r in sorted(readers):
    print(f"  - {r}")
