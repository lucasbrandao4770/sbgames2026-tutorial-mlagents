using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using Unity.MLAgents;
using Unity.MLAgents.Actuators;
using Unity.MLAgents.Sensors;

public class PressButtonAgent : Agent
{
    public event EventHandler OnAteFood;
    public event EventHandler OnEpisodeBeginEvent;

    [SerializeField] private FoodSpawner foodSpawner;
    [SerializeField] private FoodButton foodButton;

    private Rigidbody agentRigidBody;
    private float previousDistanceToFood;

    protected override void Awake()
    {
        agentRigidBody = GetComponent<Rigidbody>();
    }

    public override void OnEpisodeBegin()
    {
        transform.localPosition = new Vector3(UnityEngine.Random.Range(-2.5f, +2.5f), 0, UnityEngine.Random.Range(-2.0f, +2.0f));
        previousDistanceToFood = float.MaxValue; // Reset to a high value at the start
        OnEpisodeBeginEvent?.Invoke(this, EventArgs.Empty);
    }

    public override void CollectObservations(VectorSensor sensor)
    {
        sensor.AddObservation(foodButton.CanUseButton() ? 1 : 0);

        Vector3 dirToFoodButton = (foodButton.transform.position - transform.position).normalized;
        sensor.AddObservation(dirToFoodButton.x);
        sensor.AddObservation(dirToFoodButton.z);

        sensor.AddObservation(foodSpawner.HasFoodSpawned() ? 1 : 0);

        if (foodSpawner.HasFoodSpawned())
        {
            Vector3 dirToFood = (foodSpawner.GetLastFoodTransform().localPosition - transform.position).normalized;
            sensor.AddObservation(dirToFood.x);
            sensor.AddObservation(dirToFood.z);
        }
        else
        {
            // Food not spawned
            sensor.AddObservation(0f);
            sensor.AddObservation(0f);
        }
    }

    public override void OnActionReceived(ActionBuffers actions)
    {
        int moveX = actions.DiscreteActions[0]; // 0 = Don't Move; 1 = Left; 2 = Right
        int moveZ = actions.DiscreteActions[1]; // 0 = Don't Move; 1 = Back; 2 = Forward

        Vector3 addForce = new Vector3(0, 0, 0);

        switch (moveX)
        {
            case 0: addForce.x = 0f; break;
            case 1: addForce.x = -1f; break;
            case 2: addForce.x = +1f; break;
        }

        switch (moveZ)
        {
            case 0: addForce.z = 0f; break;
            case 1: addForce.z = -1f; break;
            case 2: addForce.z = +1f; break;
        }

        float moveSpeed = 5f;
        agentRigidBody.linearVelocity = addForce * moveSpeed + new Vector3(0, agentRigidBody.linearVelocity.y, 0);

        // Reward for moving toward the food
        if (foodSpawner.HasFoodSpawned())
        {
            float currentDistanceToFood = Vector3.Distance(transform.position, foodSpawner.GetLastFoodTransform().position);
            if (currentDistanceToFood < previousDistanceToFood)
            {
                AddReward(0.005f); // Reward for moving closer to the food
            }
            previousDistanceToFood = currentDistanceToFood; // Update the previous distance
        }

        bool isUseButtonDown = actions.DiscreteActions[2] == 1;
        if (isUseButtonDown)
        {
            // Use Action
            int layerMask = LayerMask.GetMask("Interactable"); // Replace with your FoodButton's layer
            Vector3 colliderArraySize = Vector3.one * 1.5f;
            Collider[] colliderArray = Physics.OverlapBox(transform.position, colliderArraySize, Quaternion.identity, layerMask);
            foreach (Collider collider in colliderArray)
            {
                if (collider.TryGetComponent<FoodButton>(out FoodButton foodButton))
                {
                    if (foodButton.CanUseButton())
                    {
                        foodButton.UseButton();
                        AddReward(2f); // Increased the reward for pressing the button
                    }
                }
            }
        }

        if (Vector3.Distance(transform.position, foodButton.transform.position) < 1.5f && foodButton.CanUseButton())
        {
            AddReward(-0.001f); // Small penalty for lingering near the button without pressing it
        }

        AddReward(-0.001f); // Time penalty per step
    }

    public override void Heuristic(in ActionBuffers actionsOut)
    {
        ActionSegment<int> discreteActions = actionsOut.DiscreteActions;

        switch (Mathf.RoundToInt(Input.GetAxisRaw("Horizontal")))
        {
            case -1: discreteActions[0] = 1; break;
            case 0: discreteActions[0] = 0; break;
            case +1: discreteActions[0] = 2; break;
        }

        switch (Mathf.RoundToInt(Input.GetAxisRaw("Vertical")))
        {
            case -1: discreteActions[1] = 1; break;
            case 0: discreteActions[1] = 0; break;
            case +1: discreteActions[1] = 2; break;
        }

        discreteActions[2] = Input.GetKey(KeyCode.E) ? 1 : 0; // Use Action
    }

    private void OnCollisionEnter(Collision collision)
    {
        if (collision.gameObject.TryGetComponent<Food>(out Food food))
        {
            AddReward(1f);
            Destroy(food.gameObject);
            OnAteFood?.Invoke(this, EventArgs.Empty);
            EndEpisode();
        }


        if (collision.gameObject.TryGetComponent<Wall>(out Wall wall)) {
            AddReward(-1f);
            EndEpisode();
        }
    }

}
