#!/usr/bin/env python3
"""
Simple test script to manually sync programs from PLC to database
"""
from orders.plc_service import sync_programs_from_plc

def main():
    """Run sync once"""
    print("🔄 Running PLC Program Sync")
    print("=" * 50)
    
    try:
        # Run sync
        result = sync_programs_from_plc()
        
        if result['success']:
            print("✅ Sync completed successfully!")
            print(f"📊 Statistics:")
            print(f"  Total programs: {result['total_programs']}")
            print(f"  Created: {result['created']}")
            print(f"  Updated: {result['updated']}")
            print(f"  Errors: {result['errors']}")
        else:
            print(f"❌ Sync failed: {result['error']}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
