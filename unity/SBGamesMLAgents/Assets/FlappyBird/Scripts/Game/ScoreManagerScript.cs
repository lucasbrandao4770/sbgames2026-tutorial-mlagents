using System.Collections;
using UnityEngine;

public class ScoreManagerScript : MonoBehaviour
{
    public static int Score { get; set; }
    int previousScore = -1;
    public Sprite[] numberSprites;
    public SpriteRenderer Units, Tens, Hundreds;

    void Awake()
    {
        ResetScore();
    }

	void Update () {
        if (previousScore != Score) // Save performance from non needed calculations
        {
            if(Score < 10)
            {
                // Just draw units
                Units.sprite = numberSprites[Score];
            }
            else if(Score >= 10 && Score < 100)
            {
                (Tens.gameObject as GameObject).SetActive(true);
                Tens.sprite = numberSprites[Score / 10];
                Units.sprite = numberSprites[Score % 10];
            }
            else if(Score >= 100)
            {
                if (Score >= 1000)
                    Score = 999;

                (Hundreds.gameObject as GameObject).SetActive(true);
                Hundreds.sprite = numberSprites[Score / 100];
                int rest = Score % 100;
                Tens.sprite = numberSprites[rest / 10];
                Units.sprite = numberSprites[rest % 10];
            }
        }
	}

    public void ResetScore()
    {
        // Reset the score
        Score = 0;
        previousScore = -1;

        // Deactivate Tens and Hundreds
        (Tens.gameObject as GameObject).SetActive(false);
        (Hundreds.gameObject as GameObject).SetActive(false);

        // Reset Units to 0
        Units.sprite = numberSprites[0];
    }
}
