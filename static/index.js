// Pega o domínio base e o prefixo da rota passados pelo Flask
const BASE_DOMAIN = document.body.getAttribute('data-base-domain');
const TRACKING_PATH_PREFIX = document.body.getAttribute('data-tracking-path-prefix');

document.getElementById('createLinkForm').addEventListener('submit', async function (event) {
    event.preventDefault(); // Impede o envio padrão do formulário

    const uuid = document.getElementById('uuid').value;
    const link = document.getElementById('link').value;
    const responseMessage = document.getElementById('responseMessage');
    const generatedLinkElement = document.getElementById('generatedLink');

    responseMessage.textContent = ''; // Limpa mensagens anteriores
    generatedLinkElement.innerHTML = ''; // Limpa links anteriores

    try {
        const response = await fetch('/criar', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ uuid: uuid, link: link })
        });

        if (response.ok) {
            responseMessage.textContent = 'Link criado com sucesso!';
            responseMessage.style.color = 'green';

            const fullLink = `${BASE_DOMAIN}/${TRACKING_PATH_PREFIX}/${uuid}`;

            generatedLinkElement.innerHTML = `Link para usar: <a href="${fullLink}" target="_blank">${fullLink}</a>`;
            generatedLinkElement.style.color = '#0056b3';

            document.getElementById('createLinkForm').reset(); // Limpa o formulário
            loadExistingLinks(); // Recarrega a lista de links após criar um novo
        } else {
            const errorText = await response.text();
            responseMessage.textContent = `Erro ao criar link: ${errorText}`;
            responseMessage.style.color = 'red';
        }
    } catch (error) {
        responseMessage.textContent = `Erro de conexão: ${error.message}`;
        responseMessage.style.color = 'red';
    }
});

// Função para carregar e exibir os links existentes
async function loadExistingLinks() {
    const list = document.getElementById('existingLinksList');
    list.innerHTML = '<li>Carregando links...</li>'; // Mensagem de carregamento

    try {
        const response = await fetch('/get_links');
        if (response.ok) {
            const links = await response.json();
            list.innerHTML = ''; // Limpa a mensagem de carregamento

            if (links.length === 0) {
                list.innerHTML = '<li>Nenhum link criado ainda.</li>';
            } else {
                links.forEach(item => {
                    const li = document.createElement('li');
                    const fullLink = `${BASE_DOMAIN}/${TRACKING_PATH_PREFIX}/${item.uuid}`;
                    li.innerHTML = `
                        <div>
                            <strong>UUID:</strong> ${item.uuid} <br>
                            <strong>Destino:</strong> <a href="${item.link}" target="_blank">${item.link}</a> <br>
                            <strong>Link Rastreável:</strong> <a href="${fullLink}" target="_blank">${fullLink}</a>
                        </div>
                        <button class="copy-button btn btn-sm btn-success" data-link="${fullLink}">Copiar Link</button>
                    `;
                    list.appendChild(li);
                });

                // Adiciona listeners para os botões de copiar
                document.querySelectorAll('.copy-button').forEach(button => {
                    button.addEventListener('click', function () {
                        const linkToCopy = this.getAttribute('data-link');
                        navigator.clipboard.writeText(linkToCopy).then(() => {
                            alert('Link copiado para a área de transferência!');
                        }).catch(err => {
                            console.error('Erro ao copiar link: ', err);
                            alert('Não foi possível copiar o link automaticamente. Por favor, copie manualmente: ' + linkToCopy);
                        });
                    });
                });
            }
        } else {
            list.innerHTML = `<li>Erro ao carregar links: ${response.status} ${response.statusText}</li>`;
            console.error('Erro ao carregar links existentes:', response.status, response.statusText);
        }
    } catch (error) {
        list.innerHTML = `<li>Erro de conexão: ${error.message}</li>`;
        console.error('Erro de conexão ao carregar links:', error);
    }
}

// Chama a função para carregar links quando a página é carregada
window.addEventListener('load', loadExistingLinks);
