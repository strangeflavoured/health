selector_to_html = {"a[href=\"#src.connection.docker_redis_connect\"]": "<dt class=\"sig sig-object py\" id=\"src.connection.docker_redis_connect\">\n<span class=\"sig-prename descclassname\"><span class=\"pre\">src.connection.</span></span><span class=\"sig-name descname\"><span class=\"pre\">docker_redis_connect</span></span><span class=\"sig-paren\">(</span><span class=\"sig-paren\">)</span><a class=\"reference internal\" href=\"_modules/src/connection.html#docker_redis_connect\"><span class=\"viewcode-link\"><span class=\"pre\">[source]</span></span></a></dt><dd><p>Connect to redis from inside sandbox container.</p></dd>", "a[href=\"#module-src.connection\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\">Connection<a class=\"headerlink\" href=\"#module-src.connection\" title=\"Link to this heading\">\u00b6</a></h1><p>Redis connection from inside container network.</p>"}
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
