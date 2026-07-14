const BASE =
"https://nominatim.openstreetmap.org/search";

export async function searchPlace(text){

    const url=

        `${BASE}?format=jsonv2&q=${encodeURIComponent(text)}&limit=8`;

    const response=await fetch(url,{

        headers:{

            Accept:"application/json"

        }

    });

    if(!response.ok){

        throw new Error("Search failed");

    }

    return await response.json();

}