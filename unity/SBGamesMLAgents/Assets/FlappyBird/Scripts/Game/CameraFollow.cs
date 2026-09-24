using System.Collections;
using UnityEngine;

public class CameraFollow : MonoBehaviour
{
    public Transform Player;
    float cameraZ;

	void Start () {
        cameraZ = transform.position.z;
	}

	void Update () {
        transform.position = new Vector3(Player.position.x + 0.5f, 0, cameraZ);
	}
}
