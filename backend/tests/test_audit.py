import pytest
from unittest.mock import patch
from app.services.audience_auditor import run_audience_audit

@patch('app.services.audience_auditor.collect_profile')
def test_csv_audience_audit(mock_collect):
    csv_content = "username\nuser1\nuser2\nuser3"
    
    mock_collect.side_effect = [
        {
            "collection_status": "success",
            "platform": "instagram",
            "identifier": "user1",
            "username": "user1",
            "followers": 1000,
            "following": 100,
            "posts": 10,
            "bio": "Normal bio here",
            "has_profile_picture": 1,
            "is_private": 0
        },
        {
            "collection_status": "success",
            "platform": "instagram",
            "identifier": "user2",
            "username": "user2",
            "followers": 5,
            "following": 5000,
            "posts": 0,
            "bio": "Crypto scam click link in bio",
            "has_profile_picture": 0,
            "is_private": 0
        },
        {
            "collection_status": "failed"
        }
    ]
    
    result = run_audience_audit(csv_content, target_influencer="test_target")
    
    assert result["target_influencer"] == "test_target"
    assert result["sample_size"] == 3
    assert result["successful_scans"] == 2
    assert result["valid_scans"] == 2
    assert result["fake_percentage"] == 50.0
    assert "ci_lower" in result
    assert "ci_upper" in result
    assert len(result["followers_data"]) == 3
    assert result["followers_data"][2]["status"] == "collection_failed"
