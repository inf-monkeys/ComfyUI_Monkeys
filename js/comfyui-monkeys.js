import {app} from "../../scripts/app.js";
import {$el, ComfyDialog} from "../../scripts/ui.js";
import {api} from "../../scripts/api.js"

var docStyle = document.createElement('style');
docStyle.innerHTML = `
#cm-monkeys-dialog {
	width: 600px;
	height: 520px;
	box-sizing: content-box;
	z-index: 10000;
}

.cb-widget {
	width: 400px;
	height: 25px;
	box-sizing: border-box;
	z-index: 10000;
	margin-top: 10px;
	margin-bottom: 5px;
}

.cb-widget-input {
	width: 305px;
	height: 25px;
	box-sizing: border-box;
}
.cb-widget-input:disabled {
	background-color: #444444;
	color: white;
}

.cb-widget-input-label {
	width: 90px;
	height: 25px;
	box-sizing: border-box;
	color: white;
	text-align: right;
	display: inline-block;
	margin-right: 5px;
}

.cm-monkeys-menu-container {
	column-gap: 20px;
	flex-wrap: wrap;
	box-sizing: content-box;
}

.cm-monkeys-menu-column {
	display: flex;
	flex-direction: column;
	flex: 1 1 auto;
	width: 300px;
	box-sizing: content-box;
}

.cm-title {
	background-color: black;
	text-align: center;
	height: 40px;
	width: calc(100% - 10px);
	font-weight: bold;
	justify-content: center;
	align-content: center;
	vertical-align: middle;
}

#cm-channel-badge {
	color: white;
	background-color: #AA0000;
	width: 220px;
	height: 23px;
	font-size: 13px;
	border-radius: 5px;
	left: 5px;
	top: 5px;
	align-content: center;
	justify-content: center;
	text-align: center;
	font-weight: bold;
	float: left;
	vertical-align: middle;
	position: relative;
}

#custom-nodes-grid a {
	color: #5555FF;
	font-weight: bold;
	text-decoration: none;
}

#custom-nodes-grid a:hover {
	color: #7777FF;
	text-decoration: underline;
}

#external-models-grid a {
	color: #5555FF;
	font-weight: bold;
	text-decoration: none;
}

#external-models-grid a:hover {
	color: #7777FF;
	text-decoration: underline;
}

#alternatives-grid a {
	color: #5555FF;
	font-weight: bold;
	text-decoration: none;
}

#alternatives-grid a:hover {
	color: #7777FF;
	text-decoration: underline;
}

.cm-notice-board {
	width: 290px;
	height: 270px;
	overflow: auto;
	color: var(--input-text);
	border: 1px solid var(--descrip-text);
	padding: 5px 10px;
	overflow-x: hidden;
	box-sizing: content-box;
}

.cm-notice-board > ul {
	display: block;
	list-style-type: disc;
	margin-block-start: 1em;
	margin-block-end: 1em;
	margin-inline-start: 0px;
	margin-inline-end: 0px;
	padding-inline-start: 40px;
}

.cm-conflicted-nodes-text {
	background-color: #CCCC55 !important;
	color: #AA3333 !important;
	font-size: 10px;
	border-radius: 5px;
	padding: 10px;
}

.cm-warn-note {
	background-color: #101010 !important;
	color: #FF3800 !important;
	font-size: 13px;
	border-radius: 5px;
	padding: 10px;
	overflow-x: hidden;
	overflow: auto;
}

.cm-info-note {
	background-color: #101010 !important;
	color: #FF3800 !important;
	font-size: 13px;
	border-radius: 5px;
	padding: 10px;
	overflow-x: hidden;
	overflow: auto;
}

.monkeys-form-item {
    display: flex;
    margin: 10px 0;
    justify-content: left;
    align-items: center;
}

.monkeys-form-input {
    flex-grow: 1
}

.monkeys-form-label {
    width: 200px
}
`;

document.head.appendChild(docStyle);

export var monkey_instance = null;

export function setMonkeyInstance(obj) {
    monkey_instance = obj;
}

// -----------
class MonkeysMenuDialog extends ComfyDialog {
    createS3Config() {
        let self = this;
        const enable_s3_storage = $el("input", {type: 'checkbox', id: "enableS3Storage"}, [])
        const enable_s3_storage_text = $el("label", {for: "enableS3Storage"}, ["Enable S3 Storage"])
        enable_s3_storage_text.style.color = "var(--fg-color)";
        enable_s3_storage_text.style.cursor = "pointer";
        enable_s3_storage.checked = false;

        const accessKeyIdInput = $el("input.monkeys-form-input", {type: 'password', id: "accessKeyId"}, [])
        const accessKeyIdInputText = $el("label.monkeys-form-label", {for: "accessKeyId"}, ["Access Key ID"])
        accessKeyIdInputText.style.color = "var(--fg-color)";
        accessKeyIdInputText.style.cursor = "pointer";

        const accessSecretKeyInput = $el("input.monkeys-form-input", {type: 'password', id: "accessSecretKey"}, [])
        const accessSecretKeyInputText = $el("label.monkeys-form-label", {for: "accessSecretKey"}, ["Access Secret Key"])
        accessSecretKeyInputText.style.color = "var(--fg-color)";
        accessSecretKeyInputText.style.cursor = "pointer";

        const regionInput = $el("input.monkeys-form-input", {id: "region"}, [])
        const regionInputText = $el("label.monkeys-form-label", {for: "region"}, ["Region"])
        regionInputText.style.color = "var(--fg-color)";
        regionInputText.style.cursor = "pointer";

        const endpointInput = $el("input.monkeys-form-input", {id: "endpoint"}, [])
        const endpointInputText = $el("label.monkeys-form-label", {for: "endpoint"}, ["Endpoint Url"])
        endpointInputText.style.color = "var(--fg-color)";
        endpointInputText.style.cursor = "pointer";

        const bucketInput = $el("input.monkeys-form-input", {id: "bucket"}, [])
        const bucketInputText = $el("label.monkeys-form-label", {for: "bucket"}, ["Bucket"])
        bucketInputText.style.color = "var(--fg-color)";
        bucketInputText.style.cursor = "pointer";

        const addressingStyleSelect = $el("select.monkeys-form-input", {id: "addressing_style"}, [])
        addressingStyleSelect.appendChild($el('option', {value: 'auto', text: 'auto'}, []));
        addressingStyleSelect.appendChild($el('option', {value: 'path', text: 'path'}, []));
        addressingStyleSelect.appendChild($el('option', {value: 'virtual', text: 'virtual'}, []));
        const addressingStyleSelectText = $el("label.monkeys-form-label", {for: "addressing_style"}, ["Addressing Style"])
        addressingStyleSelectText.style.color = "var(--fg-color)";
        addressingStyleSelectText.style.cursor = "pointer";

        const publicAccessUrlInput = $el("input.monkeys-form-input", {id: "public_access_url"}, [])
        const publicAccessUrlText = $el("label.monkeys-form-label", {for: "public_access_url"}, ["Public Access Url"])
        publicAccessUrlText.style.color = "var(--fg-color)";
        publicAccessUrlText.style.cursor = "pointer";


        const form = $el('form', {id: '#myForm'});

        const subMitButton = $el("button", {type: "submit", textContent: "Submit"});
        subMitButton.style.marginRight = '10px'
        const testConnectionButton = $el("button", {type: "submit", textContent: "Test Connection"});

        const getFormData = () => {
            return {
                'enabled': enable_s3_storage.checked || false,
                'aws_access_key_id': accessKeyIdInput.value || "",
                'aws_secret_access_key': accessSecretKeyInput.value || "",
                "endpoint_url": endpointInput.value || "",
                "region_name": regionInput.value || "",
                "bucket": bucketInput.value || "",
                "addressing_style": addressingStyleSelect.value || "",
                "public_access_url": publicAccessUrlInput.value || ""
            };
        }

        subMitButton.onclick = (event) => {
            event.preventDefault();
            const formData = getFormData();
            // 这里可以将formData发送到服务器端进行进一步处理
            if (formData.enabled) {
            } else {
                if (!formData.aws_access_key_id || !formData.aws_secret_access_key || !formData.endpoint_url || !formData.region_name || !formData.bucket || !publicAccessUrlInput.value) {
                    return alert("Please fill in forms")
                }
            }
            const requestOptions = {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            };
            api.fetchApi(`/monkeys/save-s3-config`, requestOptions).then(response => response.json())
                .then(data => {
                    const {success, errMsg} = data;
                    if (!success) {
                        alert("Test Connection failed: " + errMsg)
                    } else {
                        alert("Saved!")
                    }
                })
                .catch(() => alert("something went wrong"));
        }

        testConnectionButton.onclick = (event) => {
            event.preventDefault();
            const formData = getFormData();
            if (!formData.aws_access_key_id || !formData.aws_secret_access_key || !formData.endpoint_url || !formData.region_name || !formData.bucket || !formData.public_access_url) {
                return alert("Please fill in forms")
            }
            const requestOptions = {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            };
            api.fetchApi(`/monkeys/test-s3`, requestOptions).then(response => response.json())
                .then(data => {
                    const {success, errMsg} = data;
                    if (!success) {
                        alert("Test Connection failed: " + errMsg)
                    } else {
                        alert("Everything is ok!")
                    }
                })
                .catch(() => alert("something went wrong"));
        }

        form.append(
            ...[
                $el("div.monkeys-form-item", {}, [enable_s3_storage, enable_s3_storage_text]),
                $el("div.monkeys-form-item", {}, [endpointInputText, endpointInput,]),
                $el("div.monkeys-form-item", {}, [regionInputText, regionInput,]),
                $el("div.monkeys-form-item", {}, [accessKeyIdInputText, accessKeyIdInput,]),
                $el("div.monkeys-form-item", {}, [accessSecretKeyInputText, accessSecretKeyInput,]),
                $el("div.monkeys-form-item", {}, [bucketInputText, bucketInput,]),
                $el("div.monkeys-form-item", {}, [addressingStyleSelectText, addressingStyleSelect,]),
                $el("div.monkeys-form-item", {}, [publicAccessUrlText, publicAccessUrlInput,]),
                subMitButton,
                testConnectionButton
            ]
        )

        api.fetchApi("/monkeys/get-s3-config").then(response => response.json()).then(response => {
            const {success, data} = response;
            if (success) {
                enable_s3_storage.checked = data.enabled;
                endpointInput.value = data.endpoint_url;
                regionInput.value = data.region_name;
                accessKeyIdInput.value = data.aws_access_key_id;
                accessSecretKeyInput.value = data.aws_secret_access_key;
                bucketInput.value = data.bucket
                addressingStyleSelect.value = data.addressing_style;
                publicAccessUrlInput.value = data.public_access_url;
            }
        })


        return [
            $el("div", {}, [form]
            ),
            $el("br", {}, []),
        ];
    }

    constructor() {
        super();

        const close_button = $el("button", {
            id: "cm-close-button",
            type: "button",
            textContent: "Close",
            onclick: () => this.close()
        });

        const content =
            $el("div.comfy-modal-content",
                [
                    $el("tr.cm-title", {}, [
                        $el("font", {size: 6, color: "white"}, [`ComfyUI Monkeys Menu`])]
                    ),
                    $el("br", {}, []),
                    $el("div.cm-monkeys-menu-container",
                        [
                            ...this.createS3Config()
                        ]),

                    $el("br", {}, []),
                    close_button,
                ]
            );

        content.style.width = '100%';
        content.style.height = '100%';

        this.element = $el("div.comfy-modal", {id: 'cm-monkeys-dialog', parent: document.body}, [content]);
    }

    show() {
        this.element.style.display = "block";
    }
}


app.registerExtension({
    name: "Comfy.MonkeysMenu",
    init() {
    },
    async setup() {
        const menu = document.querySelector(".comfy-menu");

        const separator = document.createElement("hr");
        separator.style.margin = "20px 0";
        separator.style.width = "100%";
        menu.append(separator);


        // 创建包含按钮和 logo 的 div 元素
        const buttonContainer = document.createElement("div");
        buttonContainer.style.background = "linear-gradient(90deg, #00C9FF 0%, #92FE9D 100%)";
        buttonContainer.style.display = "flex"; // 设置 div 为 Flex 布局
        buttonContainer.style.width = "100%"
        buttonContainer.style.borderRadius = "10"

        // 创建按钮元素
        const monkeyButton = document.createElement("button");
        monkeyButton.textContent = "Monkeys";
        buttonContainer.onclick = () => {
            if (!monkey_instance)
                setMonkeyInstance(new MonkeysMenuDialog());
            monkey_instance.show();
        };
        monkeyButton.style.color = "black";
        monkeyButton.style.border = 'none'
        monkeyButton.style.outline = 'none'
        monkeyButton.style.background = "linear-gradient(90deg, #00C9FF 0%, #92FE9D 100%)";
        monkeyButton.style.flexGrow = 10

        // 创建图片元素
        const logoImg = document.createElement("img");
        logoImg.src = "https://avatars.githubusercontent.com/u/160759882?s=200&v=4";
        logoImg.alt = "Monkeys Logo"; // 添加 logo 的 alt 属性
        logoImg.style.width = "30px"; // 设置图片宽度为 10px
        logoImg.style.height = "30px"; // 设置图片高度为 10px
        logoImg.style.flexGrow = 3

        // 将按钮和 logo 图片插入到 div 内部
        buttonContainer.appendChild(logoImg);
        buttonContainer.appendChild(monkeyButton);

        // 添加鼠标悬停时的样式变化
        buttonContainer.addEventListener("mouseenter", () => {
            buttonContainer.style.cursor = "pointer"; // 鼠标悬停时鼠标样式变为手型
        });

        buttonContainer.addEventListener("mouseleave", () => {
            buttonContainer.style.cursor = "default"; // 鼠标移出时恢复默认鼠标样式
        });

        monkeyButton.addEventListener("mouseenter", () => {
            monkeyButton.style.cursor = "pointer"; // 鼠标悬停时鼠标样式变为手型
        });

        monkeyButton.addEventListener("mouseleave", () => {
            monkeyButton.style.cursor = "default"; // 鼠标移出时恢复默认鼠标样式
        });

        menu.append(buttonContainer);

    },
});