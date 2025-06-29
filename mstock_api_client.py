"""
mStock API client for interacting with the mStock Trading API.
Handles authentication, session management, and API requests.
"""

import requests
import json
import time
import logging
from typing import Dict, Any, Optional, List, Tuple

class MStockAPI:
    """
    Client for interacting with the mStock Trading API.
    Handles authentication, session management, and API requests.
    """
    
    def __init__(self, api_key: str, username: str, password: str, api_url: str, ws_url: str, version: str):
        """
        Initialize the MStockAPI client.
        
        Args:
            api_key: API key for authentication
            username: mStock account username
            password: mStock account password
            api_url: API base URL
            ws_url: WebSocket URL
            version: API version
        """
        self.api_key = api_key
        self.username = username
        self.password = password
        self.access_token = None
        self.headers = {
            "X-Mirae-Version": version,
            "Content-Type": "application/x-www-form-urlencoded"
        }
        self.base_url = api_url
        self.ws_url = ws_url
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"MStockAPI client initialized for user {username}")
        
    def login(self) -> bool:
        """
        Login to mStock API and generate access token.
        
        Returns:
            True if login successful, False otherwise
        """
        self.logger.info("Attempting API login...")
        try:
            # Step 1: Login with username and password to get OTP
            login_url = f"{self.base_url}/openapi/typea/connect/login"
            login_data = {
                "username": self.username,
                "password": self.password
            }
            self.logger.debug(f"Sending login request to {login_url} with data: {login_data}")
            
            response = requests.post(login_url, headers=self.headers, data=login_data)
            self.logger.debug(f"Login response status code: {response.status_code}")
            if response.status_code != 200:
                self.logger.error(f"Login failed (HTTP {response.status_code}): {response.text}")
                return False
                
            login_response = response.json()
            self.logger.debug(f"Login response JSON: {login_response}")
            if login_response.get("status") != "success":
                self.logger.error(f"Login failed: {login_response.get(\"message\", \"Unknown error\")}")
                return False
                
            self.logger.info("Login successful, awaiting OTP.")
            # Step 2: Get OTP from user (in production, this would be automated)
            # This input needs to be handled by the calling application (e.g., Streamlit UI)
            otp = input("Enter the OTP sent to your registered mobile number: ")
            self.logger.info("OTP received, generating session token...")
            
            # Step 3: Generate session token
            session_url = f"{self.base_url}/openapi/typea/session/token"
            session_data = {
                "api_key": self.api_key,
                "request_token": otp,
                "checksum": "L"  # This might need to be calculated based on API documentation
            }
            self.logger.debug(f"Sending session token request to {session_url} with data: {session_data}")
            
            response = requests.post(session_url, headers=self.headers, data=session_data)
            self.logger.debug(f"Session token response status code: {response.status_code}")
            if response.status_code != 200:
                self.logger.error(f"Session token generation failed (HTTP {response.status_code}): {response.text}")
                return False
                
            session_response = response.json()
            self.logger.debug(f"Session token response JSON: {session_response}")
            if session_response.get("status") != "success":
                self.logger.error(f"Session token generation failed: {session_response.get(\"message\", \"Unknown error\")}")
                return False
                
            # Save access token
            self.access_token = session_response.get("data", {}).get("access_token")
            if not self.access_token:
                self.logger.error("Access token not found in session response")
                return False
                
            # Update headers with authorization
            self.headers["Authorization"] = f"token {self.api_key}:{self.access_token}"
            self.logger.info("Session token generated successfully. Login complete.")
            return True
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error during login: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Login error: {str(e)}", exc_info=True)
            return False
            
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """
        Helper function to make API requests.
        
        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint path
            params: URL parameters
            data: Request body data
            
        Returns:
            API response JSON data or None if request fails
        """
        if not self.access_token:
            self.logger.error("Cannot make request: Not logged in (no access token)")
            return None
            
        url = f"{self.base_url}{endpoint}"
        self.logger.debug(f"Making {method} request to {url}")
        self.logger.debug(f"Headers: {self.headers}")
        if params: self.logger.debug(f"Params: {params}")
        if data: self.logger.debug(f"Data: {data}")
        
        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers, params=params)
            elif method == "POST":
                response = requests.post(url, headers=self.headers, params=params, data=data)
            else:
                self.logger.error(f"Unsupported HTTP method: {method}")
                return None
                
            self.logger.debug(f"Response status code: {response.status_code}")
            if response.status_code != 200:
                self.logger.error(f"API request failed (HTTP {response.status_code}): {response.text}")
                return None
                
            response_json = response.json()
            self.logger.debug(f"API response JSON: {response_json}")
            if response_json.get("status") != "success":
                self.logger.error(f"API request failed: {response_json.get(\"message\", \"Unknown error\")}")
                return None
                
            return response_json.get("data")
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error during API request: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"API request error: {str(e)}", exc_info=True)
            return None
            
    def get_fund_summary(self) -> Optional[Dict[str, Any]]:
        """
        Get fund summary including available funds and invested amount.
        
        Returns:
            Fund summary data or None if request fails
        """
        self.logger.info("Fetching fund summary...")
        return self._make_request("GET", "/openapi/typea/funds")
            
    def get_positions(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get current positions.
        
        Returns:
            List of position objects or None if request fails
        """
        self.logger.info("Fetching positions...")
        data = self._make_request("GET", "/openapi/typea/portfolio/positions")
        return data.get("net") if data else None
            
    def get_option_chain_master(self) -> Optional[Dict[str, Any]]:
        """
        Get option chain master data.
        
        Returns:
            Option chain master data or None if request fails
        """
        self.logger.info("Fetching option chain master...")
        return self._make_request("GET", "/openapi/typea/getoptionchainmaster/2")  # 2 is for NSE
            
    def get_option_chain(self, expiry_timestamp: str, token: str) -> Optional[Dict[str, Any]]:
        """
        Get option chain data for a specific expiry and token.
        
        Args:
            expiry_timestamp: Expiry timestamp
            token: Instrument token
            
        Returns:
            Option chain data or None if request fails
        """
        self.logger.info(f"Fetching option chain for expiry {expiry_timestamp}, token {token}...")
        endpoint = f"/openapi/typea/GetOptionChain/2/{expiry_timestamp}/{token}"
        return self._make_request("GET", endpoint)
            
    def place_order(self, order_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Place an order.
        
        Args:
            order_params: Order parameters
            
        Returns:
            Order response or None if request fails
        """
        self.logger.info(f"Placing order: {order_params}")
        return self._make_request("POST", "/openapi/typea/order/place", data=order_params)
            
    def modify_order(self, order_id: str, order_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Modify an existing order.
        
        Args:
            order_id: Order ID to modify
            order_params: New order parameters
            
        Returns:
            Order response or None if request fails
        """
        self.logger.info(f"Modifying order {order_id} with params: {order_params}")
        order_params["order_id"] = order_id
        return self._make_request("POST", "/openapi/typea/order/modify", data=order_params)
            
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an existing order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            True if cancellation successful, False otherwise
        """
        self.logger.info(f"Cancelling order {order_id}...")
        data = {"order_id": order_id}
        response_data = self._make_request("POST", "/openapi/typea/order/cancel", data=data)
        return response_data is not None
            
    def get_order_history(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get order history.
        
        Returns:
            List of orders or None if request fails
        """
        self.logger.info("Fetching order history...")
        return self._make_request("GET", "/openapi/typea/order/history")
            
    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get quote for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Quote data or None if request fails
        """
        self.logger.debug(f"Fetching quote for symbol {symbol}...")
        endpoint = f"/openapi/typea/quote/{symbol}"
        return self._make_request("GET", endpoint)
