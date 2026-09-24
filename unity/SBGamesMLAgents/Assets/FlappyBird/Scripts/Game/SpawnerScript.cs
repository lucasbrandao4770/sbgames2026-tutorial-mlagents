using System.Collections;
using UnityEngine;

public class SpawnerScript : MonoBehaviour
{
    private GameObject SpawnObject;
    public GameObject[] SpawnObjects;
    public float timeMin = 2.5f;
    public float timeMax = 3.5f;

    void Start()
    {
        SpawnObject = SpawnObjects[Random.Range(0, SpawnObjects.Length)];
        Spawn();
    }

    void Spawn()
    {
        if (GameStateManager.GameState == GameState.Playing)
        {
            // Random y position
            float y = Random.Range(-0.5f, 1f);
            GameObject go = Instantiate(SpawnObject, this.transform.position + new Vector3(0, y, 0), Quaternion.identity) as GameObject; // Original
            //GameObject go = Instantiate(SpawnObject, this.transform.position + new Vector3(0, 0, 0), Quaternion.identity) as GameObject; // Level 1
        }
        Invoke("Spawn", Random.Range(timeMin, timeMax)); // Original
        //Invoke("Spawn", 3f); // Level 1
    }
}
