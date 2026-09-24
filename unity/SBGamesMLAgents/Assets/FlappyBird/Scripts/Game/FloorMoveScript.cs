using System.Collections;
using UnityEngine;

public class FloorMoveScript : MonoBehaviour
{
    void Update()
    {
        if (GameStateManager.GameState == GameState.Dead)
            return;

        if (transform.localPosition.x < -3.9f)
        {
            transform.localPosition = new Vector3(0, transform.localPosition.y, transform.localPosition.z);
        }
        transform.Translate(-Time.deltaTime, 0, 0);
    }
}
