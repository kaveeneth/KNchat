#!/usr/bin/env python3
"""
Backend API Testing Suite for Multi-User Chat Application
Tests all backend endpoints and functionality including authentication, chat management, messaging, and file upload.
"""

import requests
import json
import base64
import time
import asyncio
import websockets
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/app/frontend/.env')

# Get backend URL from environment
BACKEND_URL = os.getenv('REACT_APP_BACKEND_URL', 'https://chatter-7.preview.emergentagent.com')
API_BASE_URL = f"{BACKEND_URL}/api"

class ChatAppTester:
    def __init__(self):
        self.users = {}  # Store user data and tokens
        self.chats = {}  # Store created chats
        self.messages = {}  # Store sent messages
        self.session = requests.Session()
        
    def log(self, message: str, level: str = "INFO"):
        """Log test messages with timestamp"""
        print(f"[{level}] {message}")
        
    def test_user_registration(self) -> bool:
        """Test user registration endpoint"""
        self.log("Testing User Registration...")
        
        # Test data for multiple users
        test_users = [
            {
                "username": "alice_johnson",
                "email": "alice.johnson@example.com", 
                "password": "SecurePass123!"
            },
            {
                "username": "bob_smith",
                "email": "bob.smith@example.com",
                "password": "MyPassword456@"
            },
            {
                "username": "charlie_brown",
                "email": "charlie.brown@example.com", 
                "password": "StrongPass789#"
            }
        ]
        
        try:
            for user_data in test_users:
                response = self.session.post(
                    f"{API_BASE_URL}/auth/register",
                    json=user_data,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.users[user_data["username"]] = {
                        "user_data": user_data,
                        "token": data["access_token"],
                        "user_info": data["user"],
                        "headers": {"Authorization": f"Bearer {data['access_token']}"}
                    }
                    self.log(f"✅ User {user_data['username']} registered successfully")
                else:
                    self.log(f"❌ Registration failed for {user_data['username']}: {response.status_code} - {response.text}", "ERROR")
                    return False
                    
            return True
            
        except Exception as e:
            self.log(f"❌ Registration test failed with exception: {str(e)}", "ERROR")
            return False
    
    def test_user_login(self) -> bool:
        """Test user login endpoint"""
        self.log("Testing User Login...")
        
        try:
            # Test login for first user
            username = "alice_johnson"
            if username not in self.users:
                self.log(f"❌ User {username} not found in registered users", "ERROR")
                return False
                
            login_data = {
                "username": username,
                "password": self.users[username]["user_data"]["password"]
            }
            
            response = self.session.post(
                f"{API_BASE_URL}/auth/login",
                json=login_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                # Update token in case it changed
                self.users[username]["token"] = data["access_token"]
                self.users[username]["headers"] = {"Authorization": f"Bearer {data['access_token']}"}
                self.log(f"✅ User {username} logged in successfully")
                return True
            else:
                self.log(f"❌ Login failed: {response.status_code} - {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Login test failed with exception: {str(e)}", "ERROR")
            return False
    
    def test_jwt_authentication(self) -> bool:
        """Test JWT token validation by accessing protected endpoint"""
        self.log("Testing JWT Authentication...")
        
        try:
            username = "alice_johnson"
            if username not in self.users:
                self.log(f"❌ User {username} not found", "ERROR")
                return False
                
            response = self.session.get(
                f"{API_BASE_URL}/users/me",
                headers=self.users[username]["headers"]
            )
            
            if response.status_code == 200:
                user_info = response.json()
                self.log(f"✅ JWT authentication successful for user: {user_info['username']}")
                return True
            else:
                self.log(f"❌ JWT authentication failed: {response.status_code} - {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ JWT authentication test failed with exception: {str(e)}", "ERROR")
            return False
    
    def test_user_search(self) -> bool:
        """Test user search functionality"""
        self.log("Testing User Search...")
        
        try:
            username = "alice_johnson"
            if username not in self.users:
                self.log(f"❌ User {username} not found", "ERROR")
                return False
                
            # Search for other users
            response = self.session.get(
                f"{API_BASE_URL}/users/search?q=bob",
                headers=self.users[username]["headers"]
            )
            
            if response.status_code == 200:
                search_results = response.json()
                if len(search_results) > 0:
                    self.log(f"✅ User search successful, found {len(search_results)} users")
                    return True
                else:
                    self.log("⚠️ User search returned no results", "WARNING")
                    return True  # Not necessarily an error if no matches
            else:
                self.log(f"❌ User search failed: {response.status_code} - {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ User search test failed with exception: {str(e)}", "ERROR")
            return False
    
    def test_private_chat_creation(self) -> bool:
        """Test creating private 1-on-1 chats"""
        self.log("Testing Private Chat Creation...")
        
        try:
            alice = "alice_johnson"
            bob = "bob_smith"
            
            if alice not in self.users or bob not in self.users:
                self.log("❌ Required users not found for chat creation", "ERROR")
                return False
            
            # Create private chat between Alice and Bob
            chat_data = {
                "name": None,
                "is_group": False,
                "participants": [self.users[bob]["user_info"]["id"]]
            }
            
            response = self.session.post(
                f"{API_BASE_URL}/chats",
                json=chat_data,
                headers=self.users[alice]["headers"]
            )
            
            if response.status_code == 200:
                chat_info = response.json()
                self.chats["private_alice_bob"] = chat_info
                self.log(f"✅ Private chat created successfully: {chat_info['id']}")
                return True
            else:
                self.log(f"❌ Private chat creation failed: {response.status_code} - {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Private chat creation test failed with exception: {str(e)}", "ERROR")
            return False
    
    def test_group_chat_creation(self) -> bool:
        """Test creating group chats"""
        self.log("Testing Group Chat Creation...")
        
        try:
            alice = "alice_johnson"
            bob = "bob_smith"
            charlie = "charlie_brown"
            
            if not all(user in self.users for user in [alice, bob, charlie]):
                self.log("❌ Required users not found for group chat creation", "ERROR")
                return False
            
            # Create group chat with all three users
            chat_data = {
                "name": "Team Discussion",
                "is_group": True,
                "participants": [
                    self.users[bob]["user_info"]["id"],
                    self.users[charlie]["user_info"]["id"]
                ]
            }
            
            response = self.session.post(
                f"{API_BASE_URL}/chats",
                json=chat_data,
                headers=self.users[alice]["headers"]
            )
            
            if response.status_code == 200:
                chat_info = response.json()
                self.chats["group_team"] = chat_info
                self.log(f"✅ Group chat created successfully: {chat_info['name']} ({chat_info['id']})")
                return True
            else:
                self.log(f"❌ Group chat creation failed: {response.status_code} - {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Group chat creation test failed with exception: {str(e)}", "ERROR")
            return False
    
    def test_get_user_chats(self) -> bool:
        """Test retrieving user's chats"""
        self.log("Testing Get User Chats...")
        
        try:
            username = "alice_johnson"
            if username not in self.users:
                self.log(f"❌ User {username} not found", "ERROR")
                return False
                
            response = self.session.get(
                f"{API_BASE_URL}/chats",
                headers=self.users[username]["headers"]
            )
            
            if response.status_code == 200:
                chats = response.json()
                self.log(f"✅ Retrieved {len(chats)} chats for user {username}")
                return True
            else:
                self.log(f"❌ Get chats failed: {response.status_code} - {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Get chats test failed with exception: {str(e)}", "ERROR")
            return False
    
    def test_send_text_message(self) -> bool:
        """Test sending text messages"""
        self.log("Testing Send Text Messages...")
        
        try:
            username = "alice_johnson"
            if username not in self.users:
                self.log(f"❌ User {username} not found", "ERROR")
                return False
            
            # Test sending message to private chat
            if "private_alice_bob" not in self.chats:
                self.log("❌ Private chat not found for messaging test", "ERROR")
                return False
            
            message_data = {
                "chat_id": self.chats["private_alice_bob"]["id"],
                "content": "Hello Bob! How are you doing today?",
                "message_type": "text"
            }
            
            response = self.session.post(
                f"{API_BASE_URL}/messages",
                json=message_data,
                headers=self.users[username]["headers"]
            )
            
            if response.status_code == 200:
                message_info = response.json()
                self.messages["text_message_1"] = message_info
                self.log(f"✅ Text message sent successfully: {message_info['id']}")
                
                # Test sending message to group chat
                if "group_team" in self.chats:
                    group_message_data = {
                        "chat_id": self.chats["group_team"]["id"],
                        "content": "Welcome to our team discussion group!",
                        "message_type": "text"
                    }
                    
                    group_response = self.session.post(
                        f"{API_BASE_URL}/messages",
                        json=group_message_data,
                        headers=self.users[username]["headers"]
                    )
                    
                    if group_response.status_code == 200:
                        self.log("✅ Group message sent successfully")
                        return True
                    else:
                        self.log(f"❌ Group message failed: {group_response.status_code}", "ERROR")
                        return False
                else:
                    return True
            else:
                self.log(f"❌ Send message failed: {response.status_code} - {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Send message test failed with exception: {str(e)}", "ERROR")
            return False
    
    def test_get_chat_messages(self) -> bool:
        """Test retrieving chat messages"""
        self.log("Testing Get Chat Messages...")
        
        try:
            username = "alice_johnson"
            if username not in self.users or "private_alice_bob" not in self.chats:
                self.log("❌ Required data not found for message retrieval test", "ERROR")
                return False
            
            chat_id = self.chats["private_alice_bob"]["id"]
            response = self.session.get(
                f"{API_BASE_URL}/messages/{chat_id}",
                headers=self.users[username]["headers"]
            )
            
            if response.status_code == 200:
                messages = response.json()
                self.log(f"✅ Retrieved {len(messages)} messages from chat")
                return True
            else:
                self.log(f"❌ Get messages failed: {response.status_code} - {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Get messages test failed with exception: {str(e)}", "ERROR")
            return False
    
    def test_file_upload(self) -> bool:
        """Test file upload functionality"""
        self.log("Testing File Upload...")
        
        try:
            username = "alice_johnson"
            if username not in self.users:
                self.log(f"❌ User {username} not found", "ERROR")
                return False
            
            # Create a test file content
            test_content = "This is a test document for file upload functionality."
            test_filename = "test_document.txt"
            
            # Prepare multipart form data
            files = {
                'file': (test_filename, test_content, 'text/plain')
            }
            
            response = self.session.post(
                f"{API_BASE_URL}/upload",
                files=files,
                headers={"Authorization": self.users[username]["headers"]["Authorization"]}
            )
            
            if response.status_code == 200:
                upload_result = response.json()
                self.log(f"✅ File upload successful: {upload_result['file_name']}")
                
                # Test sending file message
                if "private_alice_bob" in self.chats:
                    file_message_data = {
                        "chat_id": self.chats["private_alice_bob"]["id"],
                        "content": f"Shared file: {upload_result['file_name']}",
                        "message_type": "file",
                        "file_data": upload_result["file_data"],
                        "file_name": upload_result["file_name"],
                        "file_type": upload_result["file_type"]
                    }
                    
                    file_msg_response = self.session.post(
                        f"{API_BASE_URL}/messages",
                        json=file_message_data,
                        headers=self.users[username]["headers"]
                    )
                    
                    if file_msg_response.status_code == 200:
                        self.log("✅ File message sent successfully")
                        return True
                    else:
                        self.log(f"❌ File message failed: {file_msg_response.status_code}", "ERROR")
                        return False
                else:
                    return True
            else:
                self.log(f"❌ File upload failed: {response.status_code} - {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ File upload test failed with exception: {str(e)}", "ERROR")
            return False
    
    def test_websocket_connection(self) -> bool:
        """Test WebSocket connection (basic connectivity test)"""
        self.log("Testing WebSocket Connection...")
        
        try:
            username = "alice_johnson"
            if username not in self.users:
                self.log(f"❌ User {username} not found", "ERROR")
                return False
            
            user_id = self.users[username]["user_info"]["id"]
            
            # Convert HTTPS URL to WSS for WebSocket
            ws_url = BACKEND_URL.replace("https://", "wss://").replace("http://", "ws://")
            websocket_url = f"{ws_url}/ws/{user_id}"
            
            async def test_websocket():
                try:
                    async with websockets.connect(websocket_url) as websocket:
                        self.log("✅ WebSocket connection established successfully")
                        
                        # Send a ping message
                        await websocket.send("ping")
                        
                        # Wait briefly for any response
                        try:
                            response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                            self.log(f"✅ WebSocket response received: {response}")
                        except asyncio.TimeoutError:
                            self.log("✅ WebSocket connection stable (no immediate response expected)")
                        
                        return True
                except Exception as e:
                    self.log(f"❌ WebSocket connection failed: {str(e)}", "ERROR")
                    return False
            
            # Run the async WebSocket test
            result = asyncio.run(test_websocket())
            return result
            
        except Exception as e:
            self.log(f"❌ WebSocket test failed with exception: {str(e)}", "ERROR")
            return False
    
    def run_all_tests(self) -> Dict[str, bool]:
        """Run all backend tests and return results"""
        self.log("=" * 60)
        self.log("STARTING BACKEND API TESTS")
        self.log("=" * 60)
        
        test_results = {}
        
        # Test sequence - order matters for dependencies
        tests = [
            ("User Registration", self.test_user_registration),
            ("User Login", self.test_user_login),
            ("JWT Authentication", self.test_jwt_authentication),
            ("User Search", self.test_user_search),
            ("Private Chat Creation", self.test_private_chat_creation),
            ("Group Chat Creation", self.test_group_chat_creation),
            ("Get User Chats", self.test_get_user_chats),
            ("Send Text Messages", self.test_send_text_message),
            ("Get Chat Messages", self.test_get_chat_messages),
            ("File Upload", self.test_file_upload),
            ("WebSocket Connection", self.test_websocket_connection)
        ]
        
        for test_name, test_func in tests:
            self.log(f"\n--- Running {test_name} ---")
            try:
                result = test_func()
                test_results[test_name] = result
                if result:
                    self.log(f"✅ {test_name} PASSED")
                else:
                    self.log(f"❌ {test_name} FAILED")
            except Exception as e:
                self.log(f"❌ {test_name} FAILED with exception: {str(e)}", "ERROR")
                test_results[test_name] = False
            
            # Small delay between tests
            time.sleep(0.5)
        
        self.log("\n" + "=" * 60)
        self.log("BACKEND TEST RESULTS SUMMARY")
        self.log("=" * 60)
        
        passed = sum(1 for result in test_results.values() if result)
        total = len(test_results)
        
        for test_name, result in test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            self.log(f"{test_name}: {status}")
        
        self.log(f"\nOverall: {passed}/{total} tests passed")
        self.log("=" * 60)
        
        return test_results

def main():
    """Main function to run the backend tests"""
    tester = ChatAppTester()
    results = tester.run_all_tests()
    
    # Return exit code based on results
    all_passed = all(results.values())
    return 0 if all_passed else 1

if __name__ == "__main__":
    exit(main())