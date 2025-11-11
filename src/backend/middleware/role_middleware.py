from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
import google.auth.jwt as jwt

# Middleware to handle role-based access using JWT tokens
class RoleMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, audience: str):
        super().__init__(app) # Initialize the base middleware
        self.audience = audience # Audience for JWT validation

    # Process each request 
    async def dispatch(self, request: Request, call_next):
        auth_header = request.headers.get("Authorization")  
        if not auth_header.startswith("Bearer "): 
            raise ValueError("Invalid token type")
        token=auth_header.split(" ")[1]

    # Process and validate JWT token
        try:
            token_type, token = auth_header.split(" ")
            if token_type.lower() != "bearer":
                raise ValueError("Invalid token type")

            payload = jwt.decode(token, certs_url="https://www.googleapis.com/oauth2/v1/certs", audience=self.audience)
            role = payload.get("role")
            if not role:
                return JSONResponse({"detail": "Role not found in token"}, status_code=403)
            
            # Attach role and payload to request state
            request.state.user_role = role
            request.state.user_payload = payload
        
        except Exception as e:
            logging.error(f"Token validation error: {e}")
            return JSONResponse({"detail": f"Invalid token"}, status_code=401)
        
        response = await call_next(request)
        return response
