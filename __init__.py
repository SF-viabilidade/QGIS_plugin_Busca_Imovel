def classFactory(iface):
    from .busca_imovel import BuscaImovelPlugin
    return BuscaImovelPlugin(iface)