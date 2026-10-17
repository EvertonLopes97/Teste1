// Módulos fornecidos pelo runtime UXP do Premiere Pro.
// Tipos completos: @adobe/premierepro e @adobe/cc-ext-uxp-types (npm).
// O adaptador usa `any` de propósito e faz feature-detection em tempo de execução.
declare module "premierepro" {
  const ppro: any;
  export = ppro;
}
declare module "uxp" {
  const uxp: any;
  export = uxp;
}
