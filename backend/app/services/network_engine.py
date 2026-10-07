import random

def analyze_network(username: str, platform: str) -> dict:
    """
    Simulates a Network Graph Analysis (Bot Ring Detection).
    In a real scenario, this would hit the platform API to fetch followers/following,
    build a graph, and run community detection algorithms like Louvain.
    """
    # Mocking some realistic bot ring data
    node_count = random.randint(50, 150)
    suspicious_edges = random.randint(20, node_count)
    
    # Generate some mock suspicious peers
    peers = [
        {"username": f"user_{random.randint(1000, 9999)}", "risk": random.uniform(0.6, 0.99)}
        for _ in range(random.randint(3, 8))
    ]
    
    # Calculate a mock network risk score
    # High edge density + many nodes = higher bot ring probability
    network_risk = min(1.0, (suspicious_edges / node_count) + 0.2)
    
    return {
        "network_risk": network_risk,
        "nodes_analyzed": node_count,
        "suspicious_connections": suspicious_edges,
        "bot_ring_detected": network_risk > 0.7,
        "top_suspicious_peers": peers
    }
