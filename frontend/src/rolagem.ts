// No celular quem rola é a janela; no desktop é o próprio aparelho (.celular). Volta ao topo nos dois.
export function rolarParaTopo(suave = false) {
  const behavior: ScrollBehavior = suave ? "smooth" : "auto";
  window.scrollTo({ top: 0, behavior });
  document.querySelector(".celular")?.scrollTo({ top: 0, behavior });
}
