from xai_automation.services.deepseek import parse_strict_json


def test_parse_strict_json_schema_ok() -> None:
    s = """
    {
      "topic_score":80,
      "category":"ai_news",
      "viral_angle":"fast update",
      "hook":"New AI model drop",
      "audience":"builders",
      "visual_style":"clean tech",
      "content_plan":{
        "tiktok":{
          "seconds":25,
          "hook":"Hook",
          "script":"Script",
          "storyboard":[{"t":0,"duration":5,"on_screen_text":"A","voiceover":"B","visual":"C","broll":"D"}],
          "caption":"Cap",
          "hashtags":["#ai"],
          "shot_list":["Shot 1"],
          "broll_suggestions":["Broll 1"]
        },
        "instagram":{
          "reel":{
            "seconds":25,
            "hook":"Hook",
            "script":"Script",
            "storyboard":[{"t":0,"duration":5,"on_screen_text":"A","voiceover":"B","visual":"C","broll":"D"}]
          },
          "caption":"Cap",
          "cta":"CTA",
          "hashtags":["#ai"],
          "carousel":{"enabled":false,"slides":[]}
        },
        "facebook":{
          "post_long":"Post",
          "cta":"CTA",
          "hashtags":["#ai"],
          "video":{
            "seconds":25,
            "hook":"Hook",
            "script":"Script",
            "storyboard":[{"t":0,"duration":5,"on_screen_text":"A","voiceover":"B","visual":"C","broll":"D"}]
          }
        }
      }
    }
    """
    j = parse_strict_json(s)
    assert j["topic_score"] == 80
