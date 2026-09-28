using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class FoodButton : MonoBehaviour
{
    public event EventHandler OnUsed;
    [SerializeField] private FoodSpawner foodSpawner;
    [SerializeField] private Material pressedButtonMaterial;
    [SerializeField] private Material startMaterial;
    [SerializeField] private PressButtonAgent agent;

    private MeshRenderer buttonMeshRenderer;
    private Transform buttonTransform;
    private bool canUseButton;

    private void Awake()
    {
        buttonTransform = transform.Find("FoodButton");
        buttonMeshRenderer = buttonTransform.GetComponent<MeshRenderer>();
        canUseButton = true;
    }

    private void Start()
    {
        ResetButton();

        // Subscribe to OnEpisodeBeginEvent of the agent
        if (agent != null)
        {
            agent.OnEpisodeBeginEvent += HandleEpisodeBegin;
        }
    }

    private void HandleEpisodeBegin(object sender, EventArgs e)
    {
        foodSpawner.DestroyFood();
        ResetButton();
    }

    private void OnDestroy()
    {
        if (agent != null)
        {
            agent.OnEpisodeBeginEvent -= HandleEpisodeBegin;
        }
    }

    public bool CanUseButton()
    {
        return canUseButton;
    }

    public void UseButton()
    {
        if (canUseButton)
        {
            buttonMeshRenderer.material = pressedButtonMaterial;
            buttonTransform.localScale = new Vector3(1f, 0.8f, 1f);
            canUseButton = false;

            OnUsed?.Invoke(this, EventArgs.Empty);
        }
    }

    public void ResetButton()
    {
        buttonMeshRenderer.material = startMaterial;
        buttonTransform.localScale = Vector3.one;

        transform.localPosition = new Vector3(
            UnityEngine.Random.Range(5.0f, 6.5f),
            transform.localPosition.y,
            UnityEngine.Random.Range(-2.5f, 2.5f)
        );

        canUseButton = true;
    }
}
