using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using Unity.MLAgents;
using Unity.MLAgents.Actuators;
using Unity.MLAgents.Sensors;

public class MoveToGoalAgent : Agent
{
    [SerializeField] private Transform targetTransform;
    [SerializeField] private Material winMaterial;
    [SerializeField] private Material loseMaterial;
    [SerializeField] private MeshRenderer floorMeshRenderer;

    public override void OnEpisodeBegin()
    {
        transform.localPosition = new Vector3(Random.Range(-5f, 5f), 0, Random.Range(0, 6f));
        targetTransform.localPosition = new Vector3(Random.Range(-4f, 4f), 0, Random.Range(1, 5f));
    }
    public override void OnActionReceived(ActionBuffers actions)
    {
        // Apply a small negative reward for each step
        AddReward(-1f / MaxStep); // Small penalty for each step

        float moveX = actions.ContinuousActions[0];
        float moveZ = actions.ContinuousActions[1];
        float movespeed = 3f;
        transform.localPosition += new Vector3(moveX, 0, moveZ) * Time.deltaTime * movespeed;
    }

    public override void CollectObservations(VectorSensor sensor)
    {
        sensor.AddObservation(transform.localPosition); // Agent position
        sensor.AddObservation(targetTransform.localPosition); // Target position
    }

    public void OnTriggerEnter(Collider other)
    {
        if (other.TryGetComponent<Goal>(out Goal goal))
        {
            SetReward(+1f); // Positive reward for reaching the goal
            floorMeshRenderer.material = winMaterial;
            EndEpisode();
        }
        if (other.TryGetComponent<Wall>(out Wall wall))
        {
            // Calculate the penalty based on the distance to the Goal
            float distanceToGoal = Vector3.Distance(transform.localPosition, targetTransform.localPosition);
            float penalty = Mathf.Clamp(1f - (1f / (distanceToGoal + 1f)), 0.1f, 1f);
            // Clamp ensures the penalty has a minimum value (e.g., 0.1) and doesn’t go too high.

            SetReward(-penalty); // Apply scaled penalty
            floorMeshRenderer.material = loseMaterial;
            EndEpisode();
        }
    }
}
