import random

def analyze_avatar(profile_url: str, has_avatar: int) -> dict:
    """
    Simulates Image Forensics (Deepfake & Stolen Avatar Detection).
    In a real scenario, this would download the avatar, run it through a GAN artifact
    detection PyTorch model, and hit a reverse image search API (like TinEye or Google Vision).
    """
    if not has_avatar:
        return {
            "image_risk": 0.0,
            "gan_artifacts_detected": False,
            "gan_confidence": 0.0,
            "reverse_search_matches": 0,
            "status": "No avatar to analyze"
        }
        
    # Mock some image forensics data
    is_deepfake = random.choice([True, False, False]) # 33% chance
    gan_confidence = random.uniform(0.75, 0.99) if is_deepfake else random.uniform(0.01, 0.15)
    reverse_matches = random.randint(5, 50) if not is_deepfake and random.choice([True, False]) else 0
    
    # Calculate image risk
    image_risk = 0.0
    if is_deepfake:
        image_risk = gan_confidence
    elif reverse_matches > 10:
        image_risk = min(1.0, reverse_matches / 50.0)
        
    return {
        "image_risk": image_risk,
        "gan_artifacts_detected": is_deepfake,
        "gan_confidence": gan_confidence,
        "reverse_search_matches": reverse_matches,
        "status": "Deepfake Detected" if is_deepfake else ("Stolen Avatar Detected" if reverse_matches > 0 else "Authentic Image")
    }
