using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using Unity.MLAgents;
using Unity.MLAgents.Actuators;
using Unity.MLAgents.Sensors;

public class MoveToGoalAgent : Agent
{
    // Este script não sobrescreve Initialize(): não há nada para configurar uma única vez (sem
    // referências para buscar, sem eventos para assinar), então tudo acontece em OnEpisodeBegin().
    // Também não sobrescreve Heuristic(): sem controle manual por teclado, o agente só age pela
    // política treinada ou pelo treinador durante o treino.
    [SerializeField] private Transform targetTransform;
    [SerializeField] private Material winMaterial;
    [SerializeField] private Material loseMaterial;
    [SerializeField] private MeshRenderer floorMeshRenderer;

    // OnEpisodeBegin() roda no início de cada episódio, inclusive o primeiro (aqui, quando o agente
    // é criado) e todo episódio seguinte (depois de EndEpisode(), lá embaixo em OnTriggerEnter, ou ao
    // atingir o MaxStep de 1000 passos).
    // Reposiciona o agente e o alvo em pontos aleatórios, para o agente não decorar uma trajetória fixa.
    public override void OnEpisodeBegin()
    {
        transform.localPosition = new Vector3(Random.Range(-5f, 5f), 0, Random.Range(0, 6f));
        targetTransform.localPosition = new Vector3(Random.Range(-4f, 4f), 0, Random.Range(1, 5f));
    }
    // OnActionReceived roda a cada passo: o Decision Requester do prefab pede uma decisão a cada
    // 5 passos e, com Take Actions Between Decisions ligado, repete a última ação entre decisões.
    // As ações são contínuas: duas nesta configuração (mover em X e em Z), lidas de ContinuousActions.
    public override void OnActionReceived(ActionBuffers actions)
    {
        // Apply a small negative reward for each step
        // Punição pequena a cada passo, de -1/MaxStep: um episódio que chega ao limite de passos
        // acumula -1. Incentiva o agente a chegar no alvo rápido, não só a chegar.
        AddReward(-1f / MaxStep); // Small penalty for each step

        float moveX = actions.ContinuousActions[0];
        float moveZ = actions.ContinuousActions[1];
        float movespeed = 3f;
        transform.localPosition += new Vector3(moveX, 0, moveZ) * Time.deltaTime * movespeed;
    }

    // CollectObservations roda a cada decisão pedida: descreve o que o agente percebe do ambiente.
    public override void CollectObservations(VectorSensor sensor)
    {
        sensor.AddObservation(transform.localPosition); // Agent position
        sensor.AddObservation(targetTransform.localPosition); // Target position
        // Cada posição é um Vector3 (x, y, z): essas duas linhas somam 6 observações, o valor
        // configurado em Space Size no componente Behavior Parameters do prefab.
    }

    // OnTriggerEnter não é um método do ciclo de vida do Agent, é o evento de física do Unity usado
    // aqui para decidir a recompensa e encerrar o episódio.
    public void OnTriggerEnter(Collider other)
    {
        if (other.TryGetComponent<Goal>(out Goal goal))
        {
            // Tocar o alvo: recompensa fixa de +1.
            SetReward(+1f); // Positive reward for reaching the goal
            floorMeshRenderer.material = winMaterial;
            // Encerra o episódio: o ML-Agents chama OnEpisodeBegin() de novo em seguida.
            EndEpisode();
        }
        if (other.TryGetComponent<Wall>(out Wall wall))
        {
            // Calculate the penalty based on the distance to the Goal
            // Tocar uma parede: penalidade que cresce com a distância até o alvo, não um valor fixo.
            float distanceToGoal = Vector3.Distance(transform.localPosition, targetTransform.localPosition);
            float penalty = Mathf.Clamp(1f - (1f / (distanceToGoal + 1f)), 0.1f, 1f);
            // Clamp ensures the penalty has a minimum value (e.g., 0.1) and doesn’t go too high.
            // O piso de 0.1 garante uma penalidade mínima mesmo ao bater bem perto do alvo. O teto de 1
            // nunca é atingido, porque 1 - 1/(d + 1) fica sempre abaixo de 1.

            SetReward(-penalty); // Apply scaled penalty
            floorMeshRenderer.material = loseMaterial;
            EndEpisode();
        }
    }
}
