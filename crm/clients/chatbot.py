"""
HTTP client for LexFlow chatbot server integration.

This module handles all communication with the chatbot service including:
- Case classification requests
- Chat query forwarding
- Error handling with exponential backoff retry logic
- Comprehensive logging of all interactions
"""

import os
import json
import logging
import time
import requests
from datetime import datetime
from typing import Optional, Dict, Any
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logger
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class ChatbotClient:
    """
    HTTP client for communicating with the chatbot server.
    
    Features:
    - Configurable base URL via CHATBOT_URL environment variable
    - Automatic retry logic with exponential backoff
    - Request/response logging
    - Graceful degradation if chatbot unavailable
    - Timeout protection (10 seconds default)
    """
    
    def __init__(self, base_url: Optional[str] = None, timeout: int = 10, max_retries: int = 3):
        """
        Initialize the chatbot client.
        
        Args:
            base_url: Base URL for chatbot server. Defaults to CHATBOT_URL env var or http://localhost:5000
            timeout: Request timeout in seconds (default: 10)
            max_retries: Maximum number of retry attempts (default: 3)
        """
        self.base_url = (base_url or os.getenv("CHATBOT_URL", "http://localhost:5000")).rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = self._create_session()
        logger.info(f"ChatbotClient initialized with base_url={self.base_url}, timeout={timeout}s, max_retries={max_retries}")
    
    def _create_session(self) -> requests.Session:
        """
        Create a requests session with automatic retry strategy.
        
        Returns:
            Configured requests.Session with retry logic
        """
        session = requests.Session()
        
        # Retry strategy: exponential backoff for transient failures
        retry_strategy = Retry(
            total=self.max_retries,
            status_forcelist=[429, 500, 502, 503, 504],  # Retry on these HTTP codes
            allowed_methods=["GET", "POST", "PUT"],
            backoff_factor=1  # 1s, 2s, 4s, 8s backoff
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _log_request(self, method: str, endpoint: str, data: Optional[Dict] = None):
        """Log outgoing request."""
        logger.info(f"[ChatbotClient] {method} {self.base_url}{endpoint}")
        if data:
            logger.debug(f"  Request body: {json.dumps(data, default=str)}")
    
    def _log_response(self, response: requests.Response, duration: float):
        """Log incoming response."""
        logger.info(f"[ChatbotClient] Response: {response.status_code} ({duration:.2f}s)")
        if response.text:
            try:
                logger.debug(f"  Response body: {response.json()}")
            except (json.JSONDecodeError, ValueError):
                logger.debug(f"  Response body: {response.text[:200]}")
    
    def _handle_error(self, error_type: str, error_msg: str, endpoint: str) -> Dict[str, Any]:
        """
        Handle errors gracefully.
        
        Args:
            error_type: Type of error (timeout, connection, server)
            error_msg: Descriptive error message
            endpoint: The endpoint that failed
            
        Returns:
            Error response dictionary
        """
        logger.error(f"[ChatbotClient] {error_type} on {endpoint}: {error_msg}")
        return {
            "error": True,
            "error_type": error_type,
            "message": error_msg,
            "endpoint": endpoint,
            "timestamp": datetime.utcnow().isoformat(),
            "chatbot_available": False
        }
    
    def send_case_to_chatbot(self, case_id: int, case_data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Send a case to the chatbot for classification.
        
        This method POST's case data to the chatbot's /api/classify endpoint
        to get case classification, routing recommendation, and priority scoring.
        
        Args:
            case_id: ID of the case in the CRM
            case_data: Optional case data dict. If None, basic info is sent.
                      Expected keys: title, description, status, priority, etc.
        
        Returns:
            Dict containing:
            - classification: Predicted case type/category
            - confidence: Confidence score (0.0-1.0)
            - routing: Recommended assignment (lawyer_name or department)
            - priority: Recommended priority level
            - error (optional): Error details if request failed
        """
        endpoint = "/api/classify"
        url = f"{self.base_url}{endpoint}"
        
        payload = {
            "case_id": case_id,
            "case_data": case_data or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self._log_request("POST", endpoint, payload)
        start_time = time.time()
        
        try:
            response = self.session.post(
                url,
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            
            duration = time.time() - start_time
            self._log_response(response, duration)
            
            # Check for server errors
            if response.status_code >= 500:
                logger.warning(f"Chatbot server error {response.status_code}")
                return self._handle_error(
                    "server_error",
                    f"Chatbot returned {response.status_code}",
                    endpoint
                )
            
            # Successful response
            if response.status_code in [200, 201]:
                return {
                    "success": True,
                    "case_id": case_id,
                    **response.json()
                }
            else:
                return {
                    "success": False,
                    "case_id": case_id,
                    "status_code": response.status_code,
                    "message": response.text[:200] if response.text else "Unknown error"
                }
        
        except requests.exceptions.Timeout:
            return self._handle_error(
                "timeout",
                f"Chatbot request timed out after {self.timeout}s",
                endpoint
            )
        except requests.exceptions.ConnectionError as e:
            return self._handle_error(
                "connection_error",
                f"Failed to connect to chatbot: {str(e)[:100]}",
                endpoint
            )
        except requests.exceptions.RequestException as e:
            return self._handle_error(
                "request_error",
                f"Chatbot request failed: {str(e)[:100]}",
                endpoint
            )
        except Exception as e:
            logger.exception(f"Unexpected error in send_case_to_chatbot: {e}")
            return self._handle_error(
                "unexpected_error",
                f"Unexpected error: {str(e)[:100]}",
                endpoint
            )
    
    def get_chatbot_response(self, user_input: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Get a chatbot response for a user query.
        
        This method GET's from the chatbot's /api/chat endpoint with query parameters.
        Used for general chatbot interactions, FAQ, help, etc.
        
        Args:
            user_input: User's query/message
            context: Optional context dict with case_id, user_id, etc.
        
        Returns:
            Dict containing:
            - response: Chatbot's text response
            - intent: Detected user intent
            - confidence: Intent confidence (0.0-1.0)
            - error (optional): Error details if request failed
        """
        endpoint = "/api/chat"
        url = f"{self.base_url}{endpoint}"
        
        params = {
            "query": user_input,
            "timestamp": datetime.utcnow().isoformat()
        }
        if context:
            params["context"] = json.dumps(context)
        
        self._log_request("GET", endpoint, params)
        start_time = time.time()
        
        try:
            response = self.session.get(
                url,
                params=params,
                timeout=self.timeout,
                headers={"Accept": "application/json"}
            )
            
            duration = time.time() - start_time
            self._log_response(response, duration)
            
            if response.status_code >= 500:
                logger.warning(f"Chatbot server error {response.status_code}")
                return self._handle_error(
                    "server_error",
                    f"Chatbot returned {response.status_code}",
                    endpoint
                )
            
            if response.status_code in [200, 201]:
                return {
                    "success": True,
                    "query": user_input,
                    **response.json()
                }
            else:
                return {
                    "success": False,
                    "query": user_input,
                    "status_code": response.status_code,
                    "message": response.text[:200] if response.text else "Unknown error"
                }
        
        except requests.exceptions.Timeout:
            return self._handle_error(
                "timeout",
                f"Chatbot request timed out after {self.timeout}s",
                endpoint
            )
        except requests.exceptions.ConnectionError as e:
            return self._handle_error(
                "connection_error",
                f"Failed to connect to chatbot: {str(e)[:100]}",
                endpoint
            )
        except requests.exceptions.RequestException as e:
            return self._handle_error(
                "request_error",
                f"Chatbot request failed: {str(e)[:100]}",
                endpoint
            )
        except Exception as e:
            logger.exception(f"Unexpected error in get_chatbot_response: {e}")
            return self._handle_error(
                "unexpected_error",
                f"Unexpected error: {str(e)[:100]}",
                endpoint
            )
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check if the chatbot server is alive and responding.
        
        Returns:
            Dict containing:
            - healthy: True if chatbot is responding
            - status: HTTP status code
            - message: Health status message
            - timestamp: Time of check
        """
        endpoint = "/health"
        url = f"{self.base_url}{endpoint}"
        
        logger.info(f"[ChatbotClient] Health check: {url}")
        start_time = time.time()
        
        try:
            response = self.session.get(
                url,
                timeout=self.timeout,
                headers={"Accept": "application/json"}
            )
            
            duration = time.time() - start_time
            status = response.status_code
            is_healthy = 200 <= status < 300
            
            logger.info(f"[ChatbotClient] Health check result: {status} ({duration:.2f}s) - {'healthy' if is_healthy else 'unhealthy'}")
            
            return {
                "healthy": is_healthy,
                "status": status,
                "message": "Chatbot server is operational" if is_healthy else f"Unexpected status {status}",
                "timestamp": datetime.utcnow().isoformat(),
                "response_time_ms": int(duration * 1000)
            }
        
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            logger.warning("[ChatbotClient] Health check failed - chatbot unavailable")
            return {
                "healthy": False,
                "status": 0,
                "message": "Chatbot server is unavailable",
                "timestamp": datetime.utcnow().isoformat(),
                "response_time_ms": int((time.time() - start_time) * 1000)
            }
        except Exception as e:
            logger.error(f"[ChatbotClient] Health check error: {e}")
            return {
                "healthy": False,
                "status": 0,
                "message": f"Health check error: {str(e)[:100]}",
                "timestamp": datetime.utcnow().isoformat(),
                "response_time_ms": int((time.time() - start_time) * 1000)
            }


# Global client instance (lazy-initialized)
_client_instance: Optional[ChatbotClient] = None


def get_chatbot_client() -> ChatbotClient:
    """
    Get or create the global ChatbotClient instance.
    
    Returns:
        Singleton ChatbotClient instance
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = ChatbotClient()
    return _client_instance
