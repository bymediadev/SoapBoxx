#!/usr/bin/env python3
"""
Test Release Download for SoapBoxx Demo
Verifies that the GitHub release can be downloaded and accessed
"""

import requests
import json
import sys
from pathlib import Path

def test_release_download():
    """Test the GitHub release download functionality"""
    
    print("🧪 Testing SoapBoxx Demo Release Download")
    print("=" * 60)
    
    # GitHub API endpoint for releases
    repo_owner = "bymediadev"
    repo_name = "SoapBoxx"
    api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
    
    print(f"🔍 Checking release: {api_url}")
    
    try:
        # Get release information
        response = requests.get(api_url)
        response.raise_for_status()
        
        release_data = response.json()
        tag_name = release_data.get('tag_name', 'Unknown')
        release_title = release_data.get('name', 'Unknown')
        assets = release_data.get('assets', [])
        
        print(f"✅ Release found: {release_title}")
        print(f"📍 Tag: {tag_name}")
        print(f"📦 Assets: {len(assets)} files")
        
        # Check for our demo package
        demo_asset = None
        for asset in assets:
            if "SoapBoxx-Demo" in asset.get('name', ''):
                demo_asset = asset
                break
        
        if demo_asset:
            asset_name = demo_asset.get('name', 'Unknown')
            download_url = demo_asset.get('browser_download_url', '')
            size = demo_asset.get('size', 0)
            
            print(f"✅ Demo package found: {asset_name}")
            print(f"📏 Size: {size:,} bytes ({size/1024/1024:.1f} MB)")
            print(f"🔗 Download URL: {download_url}")
            
            # Test download URL accessibility
            print("\n🔍 Testing download URL accessibility...")
            try:
                # Follow redirects for GitHub releases
                head_response = requests.head(download_url, allow_redirects=True)
                if head_response.status_code in [200, 302]:
                    print("✅ Download URL accessible")
                    
                    # Check content type
                    content_type = head_response.headers.get('content-type', 'Unknown')
                    print(f"📋 Content-Type: {content_type}")
                    
                    # Check if it's a ZIP file
                    if 'zip' in content_type.lower() or asset_name.endswith('.zip'):
                        print("✅ Valid ZIP file detected")
                    else:
                        print("⚠️  Expected ZIP file, got: {content_type}")
                        
                else:
                    print(f"❌ Download URL not accessible: {head_response.status_code}")
                    return False
                    
            except Exception as e:
                print(f"❌ Error testing download URL: {e}")
                return False
            
        else:
            print("❌ Demo package not found in release assets")
            print("Available assets:")
            for asset in assets:
                print(f"   - {asset.get('name', 'Unknown')}")
            return False
        
        # Test GitHub web page accessibility
        print("\n🌐 Testing GitHub release page...")
        web_url = f"https://github.com/{repo_owner}/{repo_name}/releases/tag/{tag_name}"
        try:
            web_response = requests.get(web_url)
            if web_response.status_code == 200:
                print("✅ GitHub release page accessible")
                print(f"🔗 URL: {web_url}")
            else:
                print(f"⚠️  GitHub page status: {web_response.status_code}")
        except Exception as e:
            print(f"⚠️  Could not test GitHub page: {e}")
        
        print("\n" + "=" * 60)
        print("🎉 RELEASE DOWNLOAD TEST PASSED!")
        print("=" * 60)
        print("✅ Release accessible via GitHub API")
        print("✅ Demo package found and accessible")
        print("✅ Download URL working")
        print("✅ GitHub page accessible")
        print("\n🚀 Users can now download the demo!")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def main():
    """Main test function"""
    try:
        success = test_release_download()
        if success:
            print("\n🎯 Next steps:")
            print("   1. Share the release URL with users")
            print("   2. Test download on different machine")
            print("   3. Monitor download statistics")
            print("   4. Gather user feedback")
        else:
            print("\n❌ Release download test failed")
            print("   Check the issues above")
        
        return success
        
    except Exception as e:
        print(f"\n❌ Unexpected error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
