from typing import Dict, Optional, Any, Union, TypedDict
import httpx
import json
import uuid

# Types for arguments
ArgValue = Union[str, int, bool, None, bytes]
Args = Dict[str, ArgValue]

class TirEnvelope(TypedDict):
    version: str
    bytecode: str
    encoding: str  # "base64" | "hex" | str


class ProtoTx(TypedDict):
    tir: TirEnvelope
    args: Args


class TxEnvelope(TypedDict):
    tx: str
    bytes: Optional[str]
    encoding: str  # "base64" | "hex" | str


class ClientOptions(TypedDict, total=False):
    endpoint: str
    headers: Optional[Dict[str, str]]
    env_args: Optional[Args]


class Error(Exception):
    """Custom error for TRP operations"""
    def __init__(self, message: str, data: Any = None):
        self.message = message
        self.data = data
        super().__init__(f"{message}: {data}" if data else message)


class Client:
    def __init__(self, options: Dict[str, Any]):
        self.options = self._validate_options(options)
        self.client = httpx.AsyncClient()

    def _validate_options(self, options: Dict[str, Any]) -> ClientOptions:
        # Ensure that endpoint exists
        if 'endpoint' not in options:
            raise ValueError("The 'endpoint' option is required")
        
        validated: ClientOptions = {
            'endpoint': options['endpoint']
        }
        
        # Additional options
        if 'headers' in options:
            validated['headers'] = options['headers']
        
        if 'env_args' in options:
            validated['env_args'] = options['env_args']
            
        return validated

    async def resolve(self, proto_tx: Dict[str, Any]) -> TxEnvelope:
        """
        Resolves a transaction by sending it to the TRP server
        
        Args:
            proto_tx: The prototype transaction with its TIR and arguments
            
        Returns:
            TxEnvelope: The resolved transaction envelope
            
        Raises:
            TRPError: If there is any error resolving the transaction
        """
        # Prepare headers
        headers = {
            "Content-Type": "application/json",
        }
        
        if self.options.get('headers'):
            headers.update(self.options['headers'])
            
        # Prepare body
        body = {
            "jsonrpc": "2.0",
            "method": "trp.resolve",
            "params": {
                "tir": proto_tx.get("tir"),
                "args": proto_tx.get("args"),
                "env": self.options.get("env_args")
            },
            "id": str(uuid.uuid4())
        }
        
        try:
            # Send request
            response = await self.client.post(
                self.options['endpoint'],
                headers=headers,
                json=body
            )
            
            # Verify if the response is successful
            response.raise_for_status()
            
            # Parse response
            result = response.json()
            
            # Handle possible error
            if 'error' in result:
                raise Error(
                    result['error'].get('message', 'Unknown error'),
                    result['error'].get('data')
                )
                
            # Return result
            if 'result' not in result:
                raise Error("No result found in response")
                
            return result['result']
            
        except httpx.HTTPStatusError as e:
            raise Error(f"HTTP Error {e.response.status_code}", e.response.text)
        except httpx.RequestError as e:
            raise Error(f"Network error", str(e))
        except json.JSONDecodeError as e:
            raise Error("Error decoding JSON response", str(e))
        except Exception as e:
            raise Error(f"Unknown error", str(e))
            
    async def close(self):
        """Closes the underlying HTTP client"""
        await self.client.aclose()