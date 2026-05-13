selector_to_html = {"a[href=\"#check-resource-usage\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\">Check resource usage<a class=\"headerlink\" href=\"#check-resource-usage\" title=\"Link to this heading\">\u00b6</a></h2>", "a[href=\"#start-container\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\">Start Container<a class=\"headerlink\" href=\"#start-container\" title=\"Link to this heading\">\u00b6</a></h2><p>Instead of using <code class=\"docutils literal notranslate\"><span class=\"pre\">docker</span> <span class=\"pre\">compose</span> <span class=\"pre\">up</span></code> use the <code class=\"docutils literal notranslate\"><span class=\"pre\">compose-wrapper</span></code>:</p>", "a[href=\"#build-container\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\">Build Container<a class=\"headerlink\" href=\"#build-container\" title=\"Link to this heading\">\u00b6</a></h2>", "a[href=\"#connect-to-redis-cli\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\">Connect to Redis-CLI<a class=\"headerlink\" href=\"#connect-to-redis-cli\" title=\"Link to this heading\">\u00b6</a></h2><p>With <code class=\"docutils literal notranslate\"><span class=\"pre\">redis</span></code> container running and healthy:</p>", "a[href=\"#backup\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\">Backup<a class=\"headerlink\" href=\"#backup\" title=\"Link to this heading\">\u00b6</a></h2><p>Create a <code class=\"docutils literal notranslate\"><span class=\"pre\">dump.rdb</span></code> via the redis-cli:</p>", "a[href=\"#check-health\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\">Check health<a class=\"headerlink\" href=\"#check-health\" title=\"Link to this heading\">\u00b6</a></h2>", "a[href=\"#container-status-logs\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\">Container status/logs<a class=\"headerlink\" href=\"#container-status-logs\" title=\"Link to this heading\">\u00b6</a></h2>", "a[href=\"#container-stoppen-entfernen\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\">Container stoppen / entfernen<a class=\"headerlink\" href=\"#container-stoppen-entfernen\" title=\"Link to this heading\">\u00b6</a></h2>", "a[href=\"#docker-redis-stack-cheatsheet\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\">Docker/Redis Stack Cheatsheet<a class=\"headerlink\" href=\"#docker-redis-stack-cheatsheet\" title=\"Link to this heading\">\u00b6</a></h1><h2>Build Container<a class=\"headerlink\" href=\"#build-container\" title=\"Link to this heading\">\u00b6</a></h2>"}
skip_classes = ["headerlink", "sd-stretched-link"]

window.onload = function () {
    for (const [select, tip_html] of Object.entries(selector_to_html)) {
        const links = document.querySelectorAll(` ${select}`);
        for (const link of links) {
            if (skip_classes.some(c => link.classList.contains(c))) {
                continue;
            }

            tippy(link, {
                content: tip_html,
                allowHTML: true,
                arrow: true,
                placement: 'auto-start', maxWidth: 500, interactive: false,

            });
        };
    };
    console.log("tippy tips loaded!");
};
