using UnityEngine;
using UnityEngine.SceneManagement;

/// <summary>
/// Boot-scene owner: decides, every time TrainingHud.BootSceneName loads, whether to jump straight into a
/// scene (a trainer connected, or --scene on the command line) or show a menu in TrainingHud's visual
/// language. Installs itself once, like TrainingHud, but re-decides on every return to Boot, since
/// RuntimeInitializeOnLoadMethod only fires once, for the very first scene load of the process. The menu
/// block is centered in the window at any size (see OnGUI), not anchored to a corner.
/// </summary>
public class SceneBoot : MonoBehaviour
{
    const string SceneFlappyBird = "mainGame";
    const string SceneBasic = "Basic";
    const string SceneFoodButton = "PressButton";

    const float PanelWidth = 620f;
    const float Padding = 20f;
    const float TitleHeight = 32f;
    const float SubtitleHeight = 22f;
    const float ButtonHeight = 34f;
    // Every description row reserves two lines, so a longer text than the ones below can never grow into
    // the next button: the row always advances by this fixed height, regardless of how many lines wrap.
    const float DescriptionLineHeight = 20f;
    const int DescriptionMaxLines = 2;
    const float DescriptionHeight = DescriptionLineHeight * DescriptionMaxLines;
    const float Gap = 6f;
    const float EntryGap = 16f;
    const float ReferenceHeight = 1080f;
    const float UiScale = 1.6f;
    const float CornerMargin = 16f;

    const string Subtitle = "Jogo de demonstração do tutorial de Unity ML-Agents, SBGames 2026";

    static readonly Color PanelColor = new Color(0f, 0f, 0f, 0.7f);

    // label, target scene, areas to request (only meaningful for Basic), one-line PT-BR description (each
    // fits one line at 1024x576, and the row would still hold a second line if it ever didn't).
    static readonly (string label, string scene, int areas, string description)[] Entries =
    {
        ("FlappyBird", SceneFlappyBird, 1, "O pássaro aprende a passar pelos canos."),
        ("Basic", SceneBasic, 1, "Um agente aprende a chegar ao alvo, em uma área."),
        ("Basic com 12 áreas", SceneBasic, 12, "A mesma tarefa, em 12 áreas ao mesmo tempo."),
        ("Food/Button", SceneFoodButton, 1, "O agente aprende a apertar o botão para ganhar comida."),
    };

    static bool installed;

    /// <summary>Area count the Basic scene's TrainingAreaReplicator should use when no trainer is
    /// connected; read once by AreaCountApplier before the replicator's own Awake. Set by LoadEntry for
    /// every menu choice, so it never carries a stale value from an earlier visit.</summary>
    public static int RequestedAreaCount { get; private set; } = 1;

    bool showMenu;
    GUIStyle titleStyle;
    GUIStyle subtitleStyle;
    GUIStyle descriptionStyle;
    GUIStyle buttonStyle;
    GUIStyle versionStyle;
    // Text set in Awake (Application.version is unsafe from a field initializer); width measured once in
    // EnsureStyles, right after versionStyle exists, since the text itself never changes afterward.
    readonly GUIContent versionLabel = new GUIContent();
    float versionWidth;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Install()
    {
        if (installed)
            return;
        installed = true;
        var host = new GameObject("SceneBoot");
        DontDestroyOnLoad(host);
        host.AddComponent<SceneBoot>();
    }

    void Awake()
    {
        versionLabel.text = "v" + Application.version;
        HandleSceneLoaded(SceneManager.GetActiveScene());
    }

    void OnEnable()
    {
        SceneManager.sceneLoaded += OnSceneLoaded;
    }

    void OnDisable()
    {
        SceneManager.sceneLoaded -= OnSceneLoaded;
    }

    void OnSceneLoaded(Scene scene, LoadSceneMode mode)
    {
        HandleSceneLoaded(scene);
    }

    // Re-run every time Boot loads (first launch, and every "Menu de cenas" round trip): load a scene
    // straight away when the command line already decided one, otherwise show the menu.
    void HandleSceneLoaded(Scene scene)
    {
        showMenu = false;
        if (scene.name != TrainingHud.BootSceneName)
            return;

        if (LaunchOptions.RequestedScene != null)
        {
            string mapped = MapRequestedScene(LaunchOptions.RequestedScene);
            if (mapped != null)
            {
                RequestedAreaCount = 1;
                SceneManager.LoadScene(mapped);
                return;
            }
            Debug.Log("SceneBoot: --scene " + LaunchOptions.RequestedScene + " não reconhecido, mostrando o menu.");
        }

        if (LaunchOptions.StartedByTrainer)
        {
            SceneManager.LoadScene(SceneFlappyBird);
            return;
        }

        showMenu = true;
    }

    static string MapRequestedScene(string requested)
    {
        switch (requested.ToLowerInvariant())
        {
            case "flappybird": return SceneFlappyBird;
            case "basic": return SceneBasic;
            case "foodbutton": return SceneFoodButton;
            default: return null;
        }
    }

    void LoadEntry(int index)
    {
        RequestedAreaCount = Entries[index].areas;
        SceneManager.LoadScene(Entries[index].scene);
    }

    void OnGUI()
    {
        if (!showMenu)
            return;
        EnsureStyles();

        float scale = Mathf.Max(Screen.height, 1) / ReferenceHeight * UiScale;
        Matrix4x4 previousMatrix = GUI.matrix;
        GUI.matrix = Matrix4x4.Scale(new Vector3(scale, scale, 1f));

        // Size of the window in the same reference units the layout below is authored in, so the block
        // centers at any real window size: virtualHeight is always ReferenceHeight / UiScale, and
        // virtualWidth follows the window's actual aspect ratio.
        float virtualWidth = Screen.width / scale;
        float virtualHeight = Screen.height / scale;

        float height = PanelHeight();
        float panelX = Mathf.Max(0f, (virtualWidth - PanelWidth) * 0.5f);
        float panelY = Mathf.Max(0f, (virtualHeight - height) * 0.5f);
        Fill(new Rect(panelX, panelY, PanelWidth, height), PanelColor);

        float x = panelX + Padding;
        float width = PanelWidth - 2f * Padding;
        float y = panelY + Padding;
        GUI.Label(new Rect(x, y, width, TitleHeight), "Escolha a cena", titleStyle);
        y += TitleHeight;
        GUI.Label(new Rect(x, y, width, SubtitleHeight), Subtitle, subtitleStyle);
        y += SubtitleHeight + Gap;

        for (int i = 0; i < Entries.Length; i++)
        {
            if (GUI.Button(new Rect(x, y, width, ButtonHeight), Entries[i].label, buttonStyle))
                LoadEntry(i);
            y += ButtonHeight + Gap;
            GUI.Label(new Rect(x, y, width, DescriptionHeight), Entries[i].description, descriptionStyle);
            y += DescriptionHeight + EntryGap;
        }

        // Version, bottom-right corner of the window: same matrix as the menu block, so it scales with it,
        // but positioned from the window's own size rather than the (centered, size-varying) panel.
        var versionRect = new Rect(virtualWidth - versionWidth - CornerMargin,
            virtualHeight - SubtitleHeight - CornerMargin, versionWidth, SubtitleHeight);
        GUI.Label(versionRect, versionLabel, versionStyle);

        GUI.matrix = previousMatrix;
    }

    float PanelHeight()
    {
        return 2f * Padding + TitleHeight + SubtitleHeight + Gap
            + Entries.Length * (ButtonHeight + Gap + DescriptionHeight + EntryGap);
    }

    void Fill(Rect area, Color color)
    {
        GUI.color = color;
        GUI.DrawTexture(area, Texture2D.whiteTexture);
        GUI.color = Color.white;
    }

    void EnsureStyles()
    {
        if (titleStyle != null)
            return;
        var label = new GUIStyle(GUI.skin.label) { fontSize = 18, wordWrap = false, clipping = TextClipping.Overflow };
        label.normal.textColor = Color.white;
        titleStyle = new GUIStyle(label) { fontSize = 21, fontStyle = FontStyle.Bold };
        subtitleStyle = new GUIStyle(label) { fontSize = 14 };
        subtitleStyle.normal.textColor = new Color(1f, 1f, 1f, 0.75f);
        descriptionStyle = new GUIStyle(label) { fontSize = 15, wordWrap = true };
        descriptionStyle.normal.textColor = new Color(1f, 1f, 1f, 0.75f);
        buttonStyle = new GUIStyle(GUI.skin.button) { fontSize = 17 };
        versionStyle = new GUIStyle(label) { fontSize = 15, alignment = TextAnchor.MiddleRight };
        versionStyle.normal.textColor = new Color(1f, 1f, 1f, 0.6f);
        versionWidth = versionStyle.CalcSize(versionLabel).x + 4f;
    }
}
