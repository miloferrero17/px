import boto3

def subir_a_s3(bucket_name = "mi-bucket-milito", archivo_local = "app/temp/receta_ejemplo.pdf", nombre_en_s3 = "receta_ejemplo.pdf"):
    s3 = boto3.client("s3")

    # Subir archivo con Content-Type correcto
    s3.upload_file(
        archivo_local,
        bucket_name,
        nombre_en_s3,
        ExtraArgs={"ContentType": "application/pdf"}
    )

    # Generar URL firmada (válida por 1 hora)
    url_firmada = s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": bucket_name, "Key": nombre_en_s3},
        ExpiresIn=3600
    )

    return url_firmada


#url = subir_a_s3(archivo_local, nombre_en_s3)
#print("✅ URL firmada:", url)
