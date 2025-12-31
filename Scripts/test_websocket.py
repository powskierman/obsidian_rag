import asyncio
import websockets
import json
import os

async def test_deep_thinking():
    uri = "ws://localhost:4000/api/v1/deep-research"
    
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected!")
            
            # Send query
            query = "What is the capital of France?"  # Simple query to test connectivity
            payload = {"query": query}
            print(f"Sending query: {query}")
            await websocket.send(json.dumps(payload))
            
            # Listen for responses
            while True:
                try:
                    message = await websocket.recv()
                    data = json.loads(message)
                    
                    msg_type = data.get("type")
                    content = data.get("content")
                    
                    if msg_type == "log":
                        print(f"[LOG] {data.get('message')}")
                    elif msg_type == "status":
                        print(f"[STATUS] {content}")
                    elif msg_type == "result":
                        print("\n[RESULT] Final Answer:")
                        print(data.get("data"))
                        break
                    elif msg_type == "error":
                        print(f"[ERROR] {content}")
                        break
                    else:
                        print(f"[UNKNOWN] {data}")
                        
                except websockets.exceptions.ConnectionClosed:
                    print("Connection closed")
                    break
                except Exception as e:
                    print(f"Error receiving: {e}")
                    break
                    
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_deep_thinking())
