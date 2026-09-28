using UnityEngine;

public class FoodSpawner : MonoBehaviour
{
    [SerializeField] private GameObject foodPrefab; // Assign your Food prefab in the Inspector
    [SerializeField] private FoodButton foodButton; // Reference to the FoodButton in the Inspector

    private GameObject lastSpawnedFood;

    private void Start()
    {
        // Subscribe to the OnUsed event of the FoodButton
        if (foodButton != null)
        {
            foodButton.OnUsed += HandleButtonUsed;
        }
    }

    private void HandleButtonUsed(object sender, System.EventArgs e)
    {
        SpawnFood(); // Spawn food when the button is pressed
    }

    private void OnDestroy()
    {
        // Unsubscribe from the OnUsed event to avoid memory leaks
        if (foodButton != null)
        {
            foodButton.OnUsed -= HandleButtonUsed;
        }
    }
    public bool HasFoodSpawned()
    {
        // Returns true if food has been spawned
        return lastSpawnedFood != null;
    }

    public Transform GetLastFoodTransform()
    {
        // Returns the transform of the last spawned food
        return lastSpawnedFood != null ? lastSpawnedFood.transform : null;
    }

    public void SpawnFood()
    {
        if (lastSpawnedFood == null)
        {
            // Generate a random local position relative to the FoodSpawner
            Vector3 localSpawnPosition = new Vector3(
                UnityEngine.Random.Range(-6f, -3f),
                0,
                UnityEngine.Random.Range(-2.5f, 2.5f)
            );

            // Instantiate the food and set the parent during instantiation
            lastSpawnedFood = Instantiate(foodPrefab, transform);

            // Set the local position relative to the parent
            lastSpawnedFood.transform.localPosition = localSpawnPosition;
        }
    }

    public void DestroyFood()
    {
        // Destroys the last spawned food
        if (lastSpawnedFood != null)
        {
            Destroy(lastSpawnedFood);
            lastSpawnedFood = null;
        }
    }
}
