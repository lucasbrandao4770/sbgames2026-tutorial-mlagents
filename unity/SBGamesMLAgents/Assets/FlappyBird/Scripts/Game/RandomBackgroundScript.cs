using System.Collections;
using UnityEngine;

public class RandomBackgroundScript : MonoBehaviour
{
	public Sprite[] Backgrounds;

    void Start () {
        (GetComponent<Renderer>() as SpriteRenderer).sprite = Backgrounds[Random.Range(0, Backgrounds.Length)];
	}

}
